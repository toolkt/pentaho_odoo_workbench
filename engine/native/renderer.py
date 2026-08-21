"""Band flow + pagination: renders a parsed .prpt to PDF bytes.

Mirrors what the Pentaho classic engine does for the feature subset the
Piaggio reports use: page bands repeat on every page, the report header
renders once, one optional group partitions consecutive rows, detail rows
flow with page breaks, and the report footer flows after the last row.
"""
from __future__ import annotations

import io

from reportlab.pdfgen import canvas as rl_canvas

from .bundle import PrptBundle
from .model import Band, Element, Group, UnsupportedFeature
from .painter import Painter
from .query import prepare_sql
from .formats import format_value


def _leaf_group(group: Group) -> Group:
    """Walk a (possibly nested) group's `.child` chain down to the leaf.

    The leaf is the group that carries real `details`/`no_data` content — a
    group parsed from a <group-body> has neither (it only nests another
    group). Single-level reports have `child is None`, so the group itself
    is returned unchanged.
    """
    while group.child is not None:
        group = group.child
    return group


class NativeRenderer:
    """execute_query: callable(sql, params) -> list[dict] (one dict per row)."""

    def __init__(self, execute_query):
        self.execute_query = execute_query

    # ── public API ──────────────────────────────────────────

    def render(self, prpt_bytes: bytes, parameters: dict, output_type: str = "pdf") -> bytes:
        if output_type != "pdf":
            raise UnsupportedFeature("output type %r (native renderer is pdf-only)" % output_type)
        self._rows_cache = {}
        bundle = PrptBundle.from_bytes(prpt_bytes)
        rows = self._fetch_rows(bundle, parameters)

        buf = io.BytesIO()
        page_w, page_h = bundle.page.size_pt
        c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
        painter = Painter(c, page_h)
        flow = _Flow(bundle, painter, page_w, page_h, rows[0] if rows else {})

        self._emit_report(flow, bundle, rows, parameters)

        flow.finish()
        c.save()
        return buf.getvalue()

    # ── data ────────────────────────────────────────────────

    def _fetch_rows(self, bundle: PrptBundle, parameters: dict) -> list[dict]:
        if not bundle.sql or not bundle.has_data_bound_elements():
            return []
        # sub-report bands are measured and painted separately: cache per
        # bundle so each query hits the database once per render
        cache = getattr(self, "_rows_cache", None)
        if cache is not None and id(bundle) in cache:
            return cache[id(bundle)]
        sql, params = prepare_sql(bundle.sql, parameters)
        rows = list(self.execute_query(sql, params))
        if cache is not None:
            cache[id(bundle)] = rows
        return rows

    # ── band sequence ───────────────────────────────────────

    def _emit_report(self, flow: "_Flow", bundle: PrptBundle, rows: list[dict], parameters: dict) -> None:
        first = rows[0] if rows else {}
        last = rows[-1] if rows else {}
        subrenderer = self._subreport_emitter(parameters)
        flow.emit(bundle.report_header, first, subrenderer=subrenderer)

        if not rows:
            # the outer group's no_data is empty for a nested (group-body)
            # report — the real no-data band lives on the innermost (leaf)
            # group, exactly where a leaf top-level group already had it.
            flow.emit(_leaf_group(bundle.group).no_data, {}, subrenderer=subrenderer)
        else:
            self._emit_group(flow, bundle.group, rows, subrenderer)

        flow.emit(bundle.report_footer, last, subrenderer=subrenderer)

    def _emit_group(self, flow: "_Flow", group: Group, rows: list[dict], subrenderer) -> None:
        """Recursively emit one (possibly nested) group level over `rows`.

        Partitions `rows` on this group's own fields; for each partition,
        emits this group's header, then either recurses into the nested
        child group (group-body) or emits the leaf details band per row,
        then emits this group's footer. A leaf top-level group (child is
        None) behaves exactly as the old single-level loop did.
        """
        for part in self._partition_rows(rows, group.fields):
            flow.emit(group.header, part[0], subrenderer=subrenderer)
            if group.child is not None:
                self._emit_group(flow, group.child, part, subrenderer)
            else:
                for row in part:
                    flow.emit(group.details, row, subrenderer=subrenderer)
            flow.emit(group.footer, part[-1], subrenderer=subrenderer)

    @staticmethod
    def _partition_rows(rows: list[dict], fields: list[str]) -> list[list[dict]]:
        """Partition rows into consecutive runs of equal key(s) over `fields`."""
        if not fields:
            return [rows]
        groups: list[list[dict]] = []
        current_key = object()
        for row in rows:
            key = tuple(row.get(f) for f in fields)
            if key != current_key:
                groups.append([])
                current_key = key
            groups[-1].append(row)
        return groups

    # ── sub-reports ─────────────────────────────────────────

    def _subreport_emitter(self, parameters: dict):
        def emit_subreport(sub: PrptBundle, painter: Painter, origin_x: float, origin_y: float,
                           master_row: dict) -> float:
            rows = self._fetch_rows(sub, parameters)
            first = rows[0] if rows else dict(master_row)
            last = rows[-1] if rows else dict(master_row)
            # sub-reports have never honored group header/footer/partitioning
            # (only the details band, for every row) — preserved as-is here.
            # A nested (group-body) sub-report group has no details of its
            # own, so resolve down to the leaf group's details band.
            leaf = _leaf_group(sub.group)
            y = origin_y
            y += _paint_band(sub.report_header, painter, origin_x, y, first, emit_subreport)
            for row in rows:
                y += _paint_band(leaf.details, painter, origin_x, y, row, emit_subreport)
            y += _paint_band(sub.report_footer, painter, origin_x, y, last, emit_subreport)
            return y - origin_y

        def measure_subreport(sub: PrptBundle, origin_x: float, master_row: dict,
                              measurer) -> float:
            rows = self._fetch_rows(sub, parameters)
            first = rows[0] if rows else dict(master_row)
            last = rows[-1] if rows else dict(master_row)
            leaf = _leaf_group(sub.group)
            total = measurer(sub.report_header, first)
            for row in rows:
                total += measurer(leaf.details, row)
            total += measurer(sub.report_footer, last)
            return total

        emit_subreport.measure = measure_subreport
        return emit_subreport


# ── band measurement & painting ─────────────────────────────


def _element_text(el: Element, row: dict) -> str:
    if el.kind == "label":
        return el.value or ""
    value = row.get(el.field) if el.field else None
    return format_value(value, el.fmt)


def _side_inset(style, side: str) -> float:
    """Content inset of one band side: padding + border width (Java box model)."""
    border = style.borders.get(side)
    return style.padding.get(side, 0.0) + (border.width if border else 0.0)


def _band_height(band: Band, painter: Painter, row: dict, measure_sub=None) -> float:
    """Height of a band instance = max bottom edge of its content (+ insets)."""
    content = 0.0
    for el in band.elements:
        content = max(content, el.style.y + _element_height(el, painter, row, measure_sub))
    if band.elements:
        content += _side_inset(band.style, "top") + _side_inset(band.style, "bottom")
    return max(band.style.height, content)


def _element_height(el: Element, painter: Painter, row: dict, measure_sub=None) -> float:
    if el.kind == "band":
        inner = _band_height(Band(elements=el.elements, style=el.style), painter, row, measure_sub)
        return inner
    if el.kind == "sub-report":
        if measure_sub is None:
            return 0.0
        def measurer(band: Band, band_row: dict) -> float:
            return _band_height(band, painter, band_row, measure_sub)
        return measure_sub.measure(el.subreport, el.style.x, row, measurer)
    if el.style.height_pct is not None:
        return 0.0  # resolved against the containing band, contributes nothing
    height = el.style.height
    if el.style.dynamic_height and el.kind in ("label", "text-field", "number-field", "date-field"):
        text = _element_text(el, row)
        if text:
            height = max(height, painter.measure_text(text, el.style, el.style.width))
    return height


def _paint_band(band: Band, painter: Painter, origin_x: float, origin_y: float, row: dict,
                emit_sub=None) -> float:
    band_h = _band_height(band, painter, row, emit_sub)
    band_box = (origin_x + band.style.x, origin_y, band.style.width, band_h)
    if band.style.width:
        painter.draw_borders(band_box, band.style)

    cx = origin_x + band.style.x + _side_inset(band.style, "left")
    cy = origin_y + _side_inset(band.style, "top")
    for el in band.elements:
        _paint_element(el, painter, cx, cy, band_h, row, emit_sub)
    return band_h


def _paint_element(el: Element, painter: Painter, origin_x: float, origin_y: float,
                   band_h: float, row: dict, emit_sub=None) -> None:
    x = origin_x + el.style.x
    y = origin_y + el.style.y

    if el.kind == "band":
        inner = Band(elements=el.elements, style=el.style)
        # nested band: origin shifts by position + its own insets
        nested_h = _band_height(inner, painter, row, emit_sub)
        box = (x, y, el.style.width, nested_h)
        painter.fill_background(box, el.style)
        painter.draw_borders(box, el.style)
        cx = x + _side_inset(el.style, "left")
        cy = y + _side_inset(el.style, "top")
        for child in el.elements:
            _paint_element(child, painter, cx, cy, nested_h, row, emit_sub)
        return

    if el.kind == "sub-report":
        if emit_sub is not None:
            emit_sub(el.subreport, painter, x, y, row)
        return

    if el.style.height_pct is not None:
        height = band_h * el.style.height_pct / 100.0 - el.style.y
    else:
        height = _element_height(el, painter, row)

    box = (x, y, el.style.width, height)
    painter.fill_background(box, el.style)

    if el.kind == "horizontal-line":
        painter.draw_hline(box, el.style)
        return
    if el.kind == "vertical-line":
        painter.draw_vline(box, el.style)
        return
    if el.kind == "rectangle":
        painter.draw_rect(box, el.style)
        return
    if el.kind == "content":
        painter.draw_borders(box, el.style)
        painter.draw_image(box, el.resource, el.style)
        return
    if el.kind == "content-field":
        painter.draw_borders(box, el.style)
        painter.draw_image(box, row.get(el.field) if el.field else None, el.style)
        return
    if el.kind in ("simple-barcodes", "simple-barcode"):
        painter.draw_barcode(box, row.get(el.field), el.barcode_type, el.style)
        return

    # label / text-field / number-field / date-field
    painter.draw_borders(box, el.style)
    painter.draw_text(box, _element_text(el, row), el.style)


class _Flow:
    """Vertical flow of bands over pages, with repeating page header/footer."""

    def __init__(self, bundle: PrptBundle, painter: Painter, page_w: float, page_h: float,
                 page_band_row: dict):
        self.bundle = bundle
        self.painter = painter
        self.page_w = page_w
        self.page_h = page_h
        self.page_band_row = page_band_row
        m_top, m_left, m_bottom, m_right = bundle.page.margins
        self.margin_left = m_left
        self.margin_top = m_top
        self.header_h = _band_height(bundle.page_header, painter, page_band_row)
        self.footer_h = _band_height(bundle.page_footer, painter, page_band_row)
        self.content_top = m_top + self.header_h
        self.content_bottom = page_h - m_bottom - self.footer_h
        self.cursor: float | None = None  # None → page not started yet

    def _start_page(self) -> None:
        _paint_band(self.bundle.page_header, self.painter, self.margin_left, self.margin_top,
                    self.page_band_row)
        if self.bundle.page_footer.elements:
            _paint_band(self.bundle.page_footer, self.painter, self.margin_left,
                        self.content_bottom, self.page_band_row)
        self.cursor = self.content_top

    def emit(self, band: Band, row: dict, subrenderer=None) -> None:
        height = _band_height(band, self.painter, row, subrenderer)
        if height <= 0 and not band.elements:
            return
        if self.cursor is None:
            self._start_page()
        elif self.cursor + height > self.content_bottom and self.cursor > self.content_top:
            self.painter.c.showPage()
            self._start_page()
        _paint_band(band, self.painter, self.margin_left, self.cursor, row, subrenderer)
        self.cursor += height

    def finish(self) -> None:
        if self.cursor is None:
            self._start_page()
