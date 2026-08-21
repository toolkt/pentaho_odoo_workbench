"""Parse a .prpt bundle (zip of XML) into the native model.

Only the feature subset used by the Piaggio reports is understood; anything
else raises UnsupportedFeature so callers can surface a clear error.
"""
from __future__ import annotations

import io
import logging
import zipfile
import xml.etree.ElementTree as ET

from .model import (
    Band,
    BorderSide,
    Element,
    Group,
    PageDef,
    PlainParameter,
    Style,
    UnsupportedFeature,
)

_logger = logging.getLogger(__name__)

ELEMENT_KINDS = {
    "label",
    "text-field",
    "number-field",
    "date-field",
    "content",
    "content-field",
    "band",
    "horizontal-line",
    "vertical-line",
    "rectangle",
    "sub-report",
    "simple-barcodes",
    "simple-barcode",  # rare singular spelling seen in a few real bundles
}

# structural / non-element children that may appear inside band content.
# output-parameter is a sub-report child we don't act on (no parameter
# passing to sub-reports is implemented). "element-style" is NOT listed here
# — every call site that can see it (_parse_band_content, _parse_element)
# handles it explicitly before consulting this set, so including it here
# would be dead code.
_IGNORED_CHILDREN = {"input-parameter", "output-parameter"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _is_ignorable_child(name: str) -> bool:
    """True for structural children we deliberately do not model.

    This includes Pentaho's dynamic conditional-formatting expressions
    (``style-expression``, ``attribute-expression``, and any future
    ``*-expression``) which compute style/attribute values at report-run
    time from formulas. The native renderer does not evaluate formulas, so
    these are skipped entirely and the element keeps its static style —
    a known fidelity limitation (elements that rely solely on an expression
    for visibility/formatting will render with their design-time look).
    """
    return name in _IGNORED_CHILDREN or name.endswith("-expression")


def _attrs_by_local(node) -> dict[str, str]:
    return {_local(k): v for k, v in node.attrib.items()}


def _to_float(value: str | None, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    if value.endswith("%"):
        # Percent-of-parent spatial values (e.g. min-width="100%", a
        # right-edge x="20%") are not modeled as relative layout by this
        # renderer. Treat the numeric part as an absolute point value —
        # an approximation, but it never crashes and is exact for the
        # common "min-width=100%" (fill the band) case. min-height="%" is
        # handled separately as height_pct before reaching here.
        value = value[:-1]
    if not value:
        # a bare "%" (or otherwise empty after stripping the suffix) has no
        # numeric part to parse — fall back to the default rather than
        # raising ValueError from float("").
        return default
    return float(value)


class PrptBundle:
    def __init__(self):
        self.page = PageDef()
        self.watermark = Band()
        self.page_header = Band()
        self.page_footer = Band()
        self.report_header = Band()
        self.report_footer = Band()
        self.root_style = Style()  # layout.xml root element-style (sub-report placement)
        self.group = Group()
        self.query_name: str | None = None
        self.sql: str | None = None
        self.parameters: dict[str, PlainParameter] = {}

    # ── construction ────────────────────────────────────────

    @classmethod
    def from_bytes(cls, data: bytes) -> "PrptBundle":
        zf = zipfile.ZipFile(io.BytesIO(data))
        return cls._from_zip(zf, prefix="")

    @classmethod
    def _from_zip(cls, zf: zipfile.ZipFile, prefix: str) -> "PrptBundle":
        bundle = cls()
        bundle._zf = zf
        bundle._prefix = prefix
        bundle._parse_styles(ET.fromstring(zf.read(prefix + "styles.xml")))
        bundle._parse_layout(ET.fromstring(zf.read(prefix + "layout.xml")))
        bundle._parse_datadefinition(ET.fromstring(zf.read(prefix + "datadefinition.xml")))
        return bundle

    # ── styles.xml: page setup + page bands ─────────────────

    def _parse_styles(self, root) -> None:
        for child in root:
            name = _local(child.tag)
            if name == "page-definition":
                a = _attrs_by_local(child)
                self.page = PageDef(
                    format=a.get("pageformat", "LETTER"),
                    orientation=a.get("orientation", "portrait"),
                    margins=(
                        _to_float(a.get("margin-top")),
                        _to_float(a.get("margin-left")),
                        _to_float(a.get("margin-bottom")),
                        _to_float(a.get("margin-right")),
                    ),
                    # custom page size (no pageformat attr), e.g. BIR 612x920
                    width=_to_float(a.get("width")),
                    height=_to_float(a.get("height")),
                )
            elif name == "watermark":
                self.watermark = self._parse_band_content(child)
            elif name == "page-header":
                self.page_header = self._parse_band_content(child)
            elif name == "page-footer":
                self.page_footer = self._parse_band_content(child)

    # ── layout.xml: report bands + group ────────────────────

    def _parse_layout(self, root) -> None:
        for child in root:
            name = _local(child.tag)
            if name == "report-header":
                self.report_header = self._root_level_band(child)
            elif name == "report-footer":
                self.report_footer = self._root_level_band(child)
            elif name == "group":
                self.group = self._parse_group(child)
            elif name == "element-style":
                self.root_style = self._parse_style(child)
            else:
                raise UnsupportedFeature("layout section %r" % name)

    def _parse_group(self, node) -> Group:
        group = Group()
        gf = _attrs_by_local(node).get("group-fields", "")
        group.fields = [f for f in gf.split(",") if f]
        for child in node:
            name = _local(child.tag)
            if name == "fields":
                declared = [f.text for f in child if _local(f.tag) == "field" and f.text]
                for f in declared:
                    if f not in group.fields:
                        group.fields.append(f)
            elif name == "group-header":
                group.header = self._root_level_band(child)
            elif name == "group-footer":
                group.footer = self._root_level_band(child)
            elif name == "data-body":
                for sub in child:
                    sname = _local(sub.tag)
                    if sname == "details":
                        group.details = self._root_level_band(sub)
                    elif sname == "no-data":
                        group.no_data = self._root_level_band(sub)
                    elif sname in ("details-header", "details-footer", "element-style"):
                        continue
                    else:
                        raise UnsupportedFeature("data-body section %r" % sname)
            elif name == "group-body":
                # a group-body wraps exactly one nested <group> (multi-level
                # grouping, e.g. GL listings grouped by account then
                # sub-account) — recurse and attach it as this group's child.
                # This group itself stays a non-leaf: no details/no_data.
                #
                # Mirrors data-body's philosophy: a known-ignorable sibling
                # (element-style — seen on real group-body nodes) is skipped,
                # anything else unexpected raises. If no <group> child turns
                # up at all, this is a malformed/unsupported group-body —
                # previously this silently left group.child = None, which
                # downgrades the group to an empty leaf and silently drops
                # its data rows instead of surfacing a clear error.
                found_group = False
                for sub in child:
                    sname = _local(sub.tag)
                    if sname == "group":
                        group.child = self._parse_group(sub)
                        found_group = True
                    elif sname == "element-style":
                        continue
                    else:
                        raise UnsupportedFeature("group-body child %r" % sname)
                if not found_group:
                    raise UnsupportedFeature("group-body without a nested group")
            elif name == "element-style":
                continue
            else:
                raise UnsupportedFeature("group section %r" % name)
        return group

    def _root_level_band(self, node) -> Band:
        for child in node:
            if _local(child.tag) == "root-level-content":
                return self._parse_band_content(child)
        return Band()

    def _parse_band_content(self, node) -> Band:
        band = Band()
        for child in node:
            name = _local(child.tag)
            if name == "element-style":
                band.style = self._parse_style(child)
            elif _is_ignorable_child(name):
                continue
            else:
                band.elements.append(self._parse_element(child))
        return band

    # ── elements ────────────────────────────────────────────

    def _parse_element(self, node) -> Element:
        kind = _local(node.tag)
        if kind not in ELEMENT_KINDS:
            raise UnsupportedFeature("element %r" % kind)

        el = Element(kind=kind)
        a = _attrs_by_local(node)
        el.field = a.get("field")
        el.fmt = a.get("format") or a.get("format-string")
        if kind in ("simple-barcodes", "simple-barcode"):
            el.barcode_type = a.get("type")

        for child in node:
            cname = _local(child.tag)
            if cname == "element-style":
                el.style = self._parse_style(child)
            elif cname == "value":
                el.value = child.text or ""
            elif _is_ignorable_child(cname):
                # dynamic expressions / structural children we don't model —
                # see _is_ignorable_child. Checked before the band-recursion
                # branch below so a style-expression sibling of a band's
                # child elements is skipped rather than mis-parsed as one.
                continue
            elif kind == "band":
                el.elements.append(self._parse_element(child))
            else:
                raise UnsupportedFeature("%s child %r" % (kind, cname))

        if kind == "content":
            el.resource = self._load_resource(el.value)
        if kind == "sub-report":
            href = a.get("href", "")
            # href "/subreport/content.xml" → nested bundle dir "subreport/".
            # Pentaho always expresses href relative to the OUTERMOST bundle
            # root, even inside a nested subreport's own layout.xml — e.g. a
            # subreport living at "subreport/" has its own nested sub-report
            # href as "/subreport/subreport/content.xml", not
            # "/subreport/content.xml" relative to itself. So this must NOT
            # be prefixed with self._prefix (doing so double-nests the path
            # and looks up a part that doesn't exist).
            sub_prefix = href.strip("/").rsplit("/", 1)[0] + "/"
            # Check the nested bundle's parts actually exist before recursing.
            # A small number of real-world bundles reference a nested
            # sub-report part that isn't actually present in the archive
            # (very deep nesting / a stale export); render without that
            # sub-report rather than failing the whole report — a known
            # fidelity limitation. This check is deliberately narrow (just a
            # namelist membership test) so it does NOT swallow an unrelated
            # KeyError raised deeper inside a present sub-report's own parse.
            required = (
                sub_prefix + "styles.xml",
                sub_prefix + "layout.xml",
                sub_prefix + "datadefinition.xml",
            )
            names = self._zf.namelist()
            missing = [p for p in required if p not in names]
            if missing:
                _logger.warning(
                    "sub-report bundle part(s) %r missing; skipping sub-report", missing
                )
                el.subreport = None
            else:
                el.subreport = PrptBundle._from_zip(self._zf, sub_prefix)
                # the Java engine indents a banded sub-report by its root
                # layout x but ignores the root y (the band flows vertically)
                if not el.style.x:
                    el.style.x = el.subreport.root_style.x
        return el

    def _load_resource(self, value: str | None) -> bytes:
        """Resolve a static <content> resource-key to bytes from the bundle.

        Value looks like 'resourcekey:<loader class>;resources/image.jpeg;<meta>'.
        """
        path = None
        if value and value.startswith("resourcekey:"):
            parts = value.split(";")
            if len(parts) >= 2:
                path = parts[1]
        if not path:
            raise UnsupportedFeature("content resource %r" % (value or "")[:80])
        try:
            return self._zf.read(self._prefix + path)
        except KeyError:
            raise UnsupportedFeature("content resource file %r not in bundle" % path)

    # ── styles ──────────────────────────────────────────────

    def _parse_style(self, node) -> Style:
        style = Style()
        for part in node:
            pname = _local(part.tag)
            a = _attrs_by_local(part)
            if pname == "spatial-styles":
                style.x = _to_float(a.get("x"))
                style.y = _to_float(a.get("y"))
                style.width = _to_float(a.get("min-width"))
                mh = a.get("min-height")
                if mh and mh.endswith("%"):
                    style.height_pct = float(mh[:-1])
                else:
                    style.height = _to_float(mh)
            elif pname == "text-styles":
                style.font_face = a.get("font-face", style.font_face)
                if a.get("font-size"):
                    style.font_size = float(a["font-size"])
                style.bold = a.get("bold") == "true" or style.bold
                style.italic = a.get("italic") == "true" or style.italic
                style.underline = a.get("underline") == "true" or style.underline
            elif pname == "common-styles":
                style.align = a.get("alignment", style.align)
                style.valign = a.get("vertical-alignment", style.valign)
                # dynamic-height may live here or in content-styles
                style.dynamic_height = a.get("dynamic-height") == "true" or style.dynamic_height
                self._apply_bg_color(a, style)
            elif pname == "border-styles":
                self._parse_borders(a, style)
                self._apply_bg_color(a, style)
            elif pname == "content-styles":
                style.dynamic_height = a.get("dynamic-height") == "true" or style.dynamic_height
                style.scale = a.get("scale") == "true" or style.scale
                style.keep_aspect = a.get("keep-aspect-ratio") == "true" or style.keep_aspect
                style.draw_shape = a.get("draw-shape") == "true" or style.draw_shape
                self._apply_bg_color(a, style)
        return style

    @staticmethod
    def _apply_bg_color(a: dict[str, str], style: Style) -> None:
        # seen on border-styles in real bundles (e.g. a filled "rectangle"
        # separator bar); also accept content-styles/common-styles and the
        # "bg-color" spelling defensively, in case a report puts it there.
        color = a.get("background-color") or a.get("bg-color")
        if color:
            style.bg_color = color

    @staticmethod
    def _parse_borders(a: dict[str, str], style: Style) -> None:
        all_width = a.get("border-width")
        all_style = a.get("border-style")
        for side in ("top", "bottom", "left", "right"):
            width = _to_float(a.get("border-%s-width" % side), _to_float(all_width))
            bstyle = a.get("border-%s-style" % side) or all_style
            # a side is drawable only when it has both a width and a style
            if width > 0 and bstyle and bstyle != "none":
                style.borders[side] = BorderSide(width=width, style=bstyle)
        for side in ("top", "bottom", "left", "right"):
            pad = a.get("padding-%s" % side, a.get("padding"))
            if pad is not None:
                style.padding[side] = _to_float(pad)

    # ── datadefinition.xml: parameters + query ──────────────

    def _parse_datadefinition(self, root) -> None:
        query_name = None
        for child in root:
            name = _local(child.tag)
            if name == "parameter-definition":
                for p in child:
                    if _local(p.tag) != "plain-parameter":
                        raise UnsupportedFeature("parameter %r" % _local(p.tag))
                    a = _attrs_by_local(p)
                    param = PlainParameter(
                        name=a["name"],
                        mandatory=a.get("mandatory") == "true",
                        ptype=a.get("type", "java.lang.Object"),
                        attrs={
                            _attrs_by_local(attr).get("name", ""): (attr.text or "")
                            for attr in p
                            if _local(attr.tag) == "attribute"
                        },
                    )
                    self.parameters[param.name] = param
            elif name == "data-source":
                query_name = _attrs_by_local(child).get("report-query")

        if query_name:
            self.query_name = query_name
            self.sql = self._find_sql_query(query_name)

    def _find_sql_query(self, query_name: str) -> str | None:
        ds_prefix = self._prefix + "datasources/"
        for entry in self._zf.namelist():
            if not entry.startswith(ds_prefix) or entry.endswith("/"):
                continue
            try:
                root = ET.fromstring(self._zf.read(entry))
            except ET.ParseError:
                continue
            if _local(root.tag) != "sql-datasource":
                continue
            for qdefs in root:
                if _local(qdefs.tag) != "query-definitions":
                    continue
                for q in qdefs:
                    if _attrs_by_local(q).get("name") == query_name:
                        for sq in q:
                            if _local(sq.tag) == "static-query":
                                return sq.text
        return None

    # ── helpers ─────────────────────────────────────────────

    def has_data_bound_elements(self) -> bool:
        def walk(elements) -> bool:
            for el in elements:
                if el.field:
                    return True
                if el.elements and walk(el.elements):
                    return True
            return False

        bands = [
            self.watermark, self.page_header, self.page_footer,
            self.report_header, self.report_footer,
        ]
        # walk the whole nested-group chain — a group-body group carries no
        # details/no_data of its own (empty Bands, harmless to include), the
        # leaf group at the bottom of the chain carries the real content.
        group = self.group
        while group is not None:
            bands.extend([group.header, group.footer, group.details, group.no_data])
            group = group.child
        return any(walk(b.elements) for b in bands)
