"""Parse the two real Piaggio .prpt bundles into the native model."""
import io
import zipfile

import pytest
from pypdf import PdfReader

from conftest import DELIVERY_RECEIPT_PRPT, SALES_INVOICE_PRPT

from native.bundle import PrptBundle, _to_float
from native.model import UnsupportedFeature
from native.renderer import NativeRenderer


@pytest.fixture(scope="module")
def dr():
    return PrptBundle.from_bytes(DELIVERY_RECEIPT_PRPT.read_bytes())


@pytest.fixture(scope="module")
def si():
    return PrptBundle.from_bytes(SALES_INVOICE_PRPT.read_bytes())


# ── page setup ──────────────────────────────────────────────

def test_dr_page_definition(dr):
    assert dr.page.format == "LETTER"
    assert dr.page.orientation == "portrait"
    assert dr.page.margins == (0.0, 0.0, 0.0, 0.0)
    assert dr.page.size_pt == (612.0, 792.0)


def test_si_page_definition(si):
    assert si.page.format == "LETTER"
    assert si.page.orientation == "landscape"
    assert si.page.margins == (36.0, 36.0, 36.0, 36.0)
    assert si.page.size_pt == (792.0, 612.0)


# ── page formats (Port 4 FIX 1) ─────────────────────────────
#
# Rectangles verified against the Java engine's own
# org.pentaho.reporting.engine.classic.core.util.PageSize class (decompiled
# from pentaho-reporting-engine-classic-core-5.0-SNAPSHOT.jar's <clinit>).

def test_new_page_formats_size_pt():
    from native.model import PageDef

    assert PageDef(format="FOLIO").size_pt == (595.0, 935.0)
    assert PageDef(format="LEDGER").size_pt == (1224.0, 792.0)
    assert PageDef(format="TABLOID").size_pt == (792.0, 1224.0)
    assert PageDef(format="LETTER_ROTATED").size_pt == (792.0, 612.0)
    assert PageDef(format="LETTER_EXTRA").size_pt == (684.0, 864.0)
    assert PageDef(format="LEGAL_EXTRA").size_pt == (684.0, 1080.0)
    assert PageDef(format="FANFOLDGERMANLEGAL").size_pt == (612.0, 936.0)
    assert PageDef(format="A4_ROTATED").size_pt == (842.0, 595.0)
    # also present in the sample_prpt/ corpus but not in the task's list —
    # added after the corpus scan turned them up
    assert PageDef(format="STATEMENT").size_pt == (396.0, 612.0)
    assert PageDef(format="PAPER9X12").size_pt == (648.0, 864.0)
    assert PageDef(format="PAPER8X10").size_pt == (576.0, 720.0)


def test_folio_landscape_swaps_dimensions():
    from native.model import PageDef

    assert PageDef(format="FOLIO", orientation="landscape").size_pt == (935.0, 595.0)


def test_unknown_page_format_falls_back_to_letter_without_crashing():
    from native.model import PageDef

    # a page format the renderer has never seen must never crash the
    # render — fall back to LETTER instead of raising (previously this
    # KeyError propagated as UnsupportedFeature and failed the whole report).
    assert PageDef(format="SOME_FUTURE_FORMAT_NOBODY_HAS_SEEN").size_pt == (612.0, 792.0)


# ── delivery receipt structure ──────────────────────────────

def test_dr_page_header_elements(dr):
    kinds = [e.kind for e in dr.page_header.elements]
    assert kinds.count("label") == 2
    assert kinds.count("text-field") == 2
    assert kinds.count("content-field") == 1
    title = next(e for e in dr.page_header.elements if e.value == "DELIVERY RECEIPT")
    assert title.style.font_size == 20
    assert title.style.bold is True
    assert title.style.align == "center"
    logo = next(e for e in dr.page_header.elements if e.kind == "content-field")
    assert logo.field == "company_logo"
    assert logo.style.scale is True
    assert logo.style.keep_aspect is True


def test_dr_report_header(dr):
    els = dr.report_header.elements
    assert len(els) == 16
    labels = {e.value for e in els if e.kind == "label"}
    assert {"NAME:", "PRODUCT", "SERIAL NO.", "QTY", "UOM", "PRICE", "AMOUNT"} <= labels
    fields = {e.field for e in els if e.kind == "text-field"}
    assert fields == {"dr_date", "order_number", "vendor_name", "vendor_address", "mobile_number"}


def test_dr_details_row(dr):
    assert dr.group.fields == []
    row_bands = dr.group.details.elements
    assert len(row_bands) == 1
    row = row_bands[0]
    assert row.kind == "band"
    assert row.style.dynamic_height is True
    cells = {e.field: e for e in row.elements}
    assert set(cells) == {"quantity", "product_name", "price", "amount", "serial_number", "uom"}
    assert cells["quantity"].kind == "number-field"
    assert cells["product_name"].kind == "text-field"
    # cells stretch to the full (dynamic) row height
    assert cells["product_name"].style.height_pct == 100.0
    assert cells["product_name"].style.padding["left"] == 3.0
    # per-side borders
    assert cells["product_name"].style.borders["bottom"].width == 1.0
    assert "top" not in cells["product_name"].style.borders


def test_dr_subreport_is_static(dr):
    subs = [e for e in dr.report_footer.elements if e.kind == "sub-report"]
    assert len(subs) == 1
    sub = subs[0].subreport
    assert sub is not None
    foot = sub.report_footer.elements
    assert [e.kind for e in foot].count("horizontal-line") == 2
    assert "Customer's Signature" in {e.value for e in foot if e.kind == "label"}
    # nothing in the sub-report is bound to a data field → its query is never needed
    assert sub.has_data_bound_elements() is False


def test_dr_query_and_parameters(dr):
    assert dr.query_name == "Query 1"
    assert "WHERE sp.id IN (${ids})" in dr.sql
    assert set(dr.parameters) == {"ids"}
    assert dr.parameters["ids"].mandatory is False


# ── sales invoice structure ─────────────────────────────────

def test_si_group_fields(si):
    assert si.group.fields == ["move_id"]
    assert si.report_header.elements == []


def test_si_group_header(si):
    els = si.group.header.elements
    assert "SALES INVOICE" in {e.value for e in els if e.kind == "label"}
    assert "invoice_number" in {e.field for e in els if e.kind == "text-field"}
    # the boxed registered_name sits inside a nested band
    bands = [e for e in els if e.kind == "band"]
    nested_fields = {e.field for b in bands for e in b.elements}
    assert "registered_name" in nested_fields


def test_si_details_row(si):
    row = si.group.details.elements[0]
    cells = {e.field: e.kind for e in row.elements}
    assert cells == {
        "description": "text-field",
        "quantity": "number-field",
        "price_unit": "number-field",
        "amount": "number-field",
        "uom": "text-field",
        "serial_numbers": "text-field",
    }


def test_si_group_footer_totals(si):
    fields = [e.field for e in si.group.footer.elements if e.kind == "number-field"]
    assert fields.count("vat_amount") == 3
    assert fields.count("total_amount_due") == 2
    assert "vatable_sales" in fields
    assert "withholding_tax" in fields


def test_si_query(si):
    assert "WHERE am.id IN (${ids})" in si.sql


def test_dynamic_height_parsed_from_common_styles():
    # in real .prpt files dynamic-height sits in <common-styles>, not
    # <content-styles> (e.g. the AP voucher vendor_address field)
    from conftest import AP_VOUCHER_PRPT

    from native.bundle import PrptBundle

    bundle = PrptBundle.from_bytes(AP_VOUCHER_PRPT.read_bytes())
    by_field = {el.field: el for el in bundle.page_header.elements if el.field}
    assert by_field["vendor_address"].style.dynamic_height is True
    assert by_field["company_address"].style.dynamic_height is True


def test_bir_2307_parses_with_content_and_custom_page():
    # BIR 2307: custom page size (612x920, no named format) and a static
    # <content> element carrying the scanned government form as background
    from conftest import BIR_2307_PRPT

    from native.bundle import PrptBundle

    bundle = PrptBundle.from_bytes(BIR_2307_PRPT.read_bytes())
    assert bundle.page.size_pt == (612.0, 920.0)
    contents = [el for el in bundle.report_header.elements if el.kind == "content"]
    assert len(contents) == 1
    assert contents[0].resource is not None
    assert contents[0].resource[:2] == b"\xff\xd8"  # JPEG magic
    assert contents[0].style.width == 601.0
    # two banded sub-reports with their own SQL
    subs = [el for el in _walk(bundle.report_header.elements) if el.kind == "sub-report"]
    assert len(subs) == 2
    assert all(s.subreport.sql for s in subs)


def _walk(elements):
    for el in elements:
        yield el
        if el.elements:
            yield from _walk(el.elements)


# ── synthetic bundle helpers ─────────────────────────────────
#
# These build small, self-contained .prpt zips in-memory (real Pentaho
# .prpt files are just zips of XML "parts" — no need for the external
# sample_prpt/ corpus or the piaggio_reports/ fixtures to exercise the
# parser). The root tag of each of styles.xml / layout.xml /
# datadefinition.xml is never inspected by the parser (only its
# children are), so a bare `<r>...</r>` wrapper is enough everywhere.

def _make_prpt(parts: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in parts.items():
            zf.writestr(path, content)
    return buf.getvalue()


def _sql_datasource_part(query_name: str, sql: str) -> str:
    return (
        "<sql-datasource><query-definitions>"
        '<query name="%s"><static-query>%s</static-query></query>'
        "</query-definitions></sql-datasource>" % (query_name, sql)
    )


# ── sub-report sibling resolution ────────────────────────────

def test_subreport_siblings_resolve_to_distinct_bundles():
    # outer bundle → "subreport/" → two SIBLING subreports at
    # "subreport/subreport/" and "subreport/subreport1/", each with its
    # own query. This is the real-world shape (confirmed against
    # sample_prpt/tk-dms__invoice.prpt): href is always root-relative,
    # even from within a nested subreport's own layout.xml.
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            '<sub-report href="/subreport/content.xml">'
            "<element-style>"
            '<spatial-styles x="0" y="0" min-width="100" min-height="20"/>'
            "</element-style>"
            "</sub-report>"
            "</root-level-content></report-header></r>"
        ),
        "subreport/styles.xml": "<r/>",
        "subreport/datadefinition.xml": "<r/>",
        "subreport/layout.xml": (
            "<r><report-header><root-level-content>"
            '<sub-report href="/subreport/subreport/content.xml">'
            "<element-style>"
            '<spatial-styles x="0" y="0" min-width="50" min-height="10"/>'
            "</element-style>"
            "</sub-report>"
            '<sub-report href="/subreport/subreport1/content.xml">'
            "<element-style>"
            '<spatial-styles x="0" y="20" min-width="50" min-height="10"/>'
            "</element-style>"
            "</sub-report>"
            "</root-level-content></report-header></r>"
        ),
        "subreport/subreport/styles.xml": "<r/>",
        "subreport/subreport/layout.xml": "<r/>",
        "subreport/subreport/datadefinition.xml": (
            '<r><data-source report-query="QueryA"/></r>'
        ),
        "subreport/subreport/datasources/ds.xml": _sql_datasource_part(
            "QueryA", "SELECT 'A' AS marker"
        ),
        "subreport/subreport1/styles.xml": "<r/>",
        "subreport/subreport1/layout.xml": "<r/>",
        "subreport/subreport1/datadefinition.xml": (
            '<r><data-source report-query="QueryB"/></r>'
        ),
        "subreport/subreport1/datasources/ds.xml": _sql_datasource_part(
            "QueryB", "SELECT 'B' AS marker"
        ),
    }
    bundle = PrptBundle.from_bytes(_make_prpt(parts))

    top_sub = bundle.report_header.elements[0]
    assert top_sub.kind == "sub-report"
    mid = top_sub.subreport
    assert mid is not None

    mid_subs = [e for e in mid.report_header.elements if e.kind == "sub-report"]
    assert len(mid_subs) == 2
    a, b = mid_subs[0].subreport, mid_subs[1].subreport
    assert a is not None and b is not None

    # distinct bundles, not a collision / KeyError, and not the same object
    assert a is not b
    assert {a.query_name, b.query_name} == {"QueryA", "QueryB"}
    by_name = {a.query_name: a, b.query_name: b}
    assert "'A'" in by_name["QueryA"].sql
    assert "'B'" in by_name["QueryB"].sql
    assert by_name["QueryA"].sql != by_name["QueryB"].sql


def test_subreport_missing_part_skips_gracefully():
    # href points at a sub-report dir that was never written into the
    # archive (stale export / deep nesting) — render without it rather
    # than raising.
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            '<sub-report href="/missing/content.xml">'
            "<element-style>"
            '<spatial-styles x="0" y="0" min-width="10" min-height="10"/>'
            "</element-style>"
            "</sub-report>"
            "</root-level-content></report-header></r>"
        ),
    }
    bundle = PrptBundle.from_bytes(_make_prpt(parts))
    sub_el = bundle.report_header.elements[0]
    assert sub_el.kind == "sub-report"
    assert sub_el.subreport is None


# ── *-expression children are skipped, not mis-parsed ────────

def test_style_and_attribute_expression_children_are_skipped():
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            "<label>"
            "<element-style>"
            '<spatial-styles x="0" y="0" min-width="100" min-height="20"/>'
            "</element-style>"
            '<style-expression name="color"><formula>UPPER("x")</formula></style-expression>'
            '<attribute-expression name="visible"><formula>TRUE()</formula></attribute-expression>'
            "<value>Hello</value>"
            "</label>"
            "</root-level-content></report-header></r>"
        ),
    }
    bundle = PrptBundle.from_bytes(_make_prpt(parts))
    els = bundle.report_header.elements
    assert len(els) == 1
    assert els[0].kind == "label"
    assert els[0].value == "Hello"


# ── "%" spatial values parse without ValueError ──────────────

def test_percent_spatial_values_parse():
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            "<label>"
            "<element-style>"
            '<spatial-styles x="50%" y="0" min-width="100%" min-height="20"/>'
            "</element-style>"
            "<value>Hi</value>"
            "</label>"
            "</root-level-content></report-header></r>"
        ),
    }
    bundle = PrptBundle.from_bytes(_make_prpt(parts))
    el = bundle.report_header.elements[0]
    assert el.style.x == 50.0
    assert el.style.width == 100.0


def test_to_float_bare_percent_returns_default():
    # a bare "%" (or empty-after-strip) must not raise float("")
    assert _to_float("%") == 0.0
    assert _to_float("%", default=5.0) == 5.0
    assert _to_float("") == 0.0
    assert _to_float(None, default=3.0) == 3.0
    assert _to_float("42%") == 42.0


# ── vertical-line + rectangle ─────────────────────────────────

def test_vertical_line_and_rectangle_parse():
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            "<vertical-line>"
            "<element-style>"
            '<spatial-styles x="10" y="0" min-width="0" min-height="30"/>'
            "</element-style>"
            "</vertical-line>"
            "<rectangle>"
            "<element-style>"
            '<content-styles draw-shape="true"/>'
            '<spatial-styles x="0" y="0" min-width="100" min-height="30"/>'
            "</element-style>"
            "</rectangle>"
            "</root-level-content></report-header></r>"
        ),
    }
    bundle = PrptBundle.from_bytes(_make_prpt(parts))
    kinds = [e.kind for e in bundle.report_header.elements]
    assert kinds.count("vertical-line") == 1
    assert kinds.count("rectangle") == 1
    rect = next(e for e in bundle.report_header.elements if e.kind == "rectangle")
    assert rect.style.draw_shape is True


# ── rectangle background-color fill (Port-2 fix-round) ───────
#
# Real "colored separator bar" rectangles carry background-color on
# border-styles, no draw-shape, and stroke-style="none" (confirmed against
# sample_prpt/Icademy ERP__confirmation_of_employment.prpt) — before this
# fix they parsed but rendered as nothing (fill silently dropped).

def test_rectangle_background_color_parses():
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            "<rectangle>"
            "<element-style>"
            '<border-styles background-color="#c9c98b"/>'
            '<content-styles scale="true" stroke-style="none"/>'
            '<spatial-styles x="0" y="65" min-width="531" min-height="15"/>'
            "</element-style>"
            "</rectangle>"
            "</root-level-content></report-header></r>"
        ),
    }
    bundle = PrptBundle.from_bytes(_make_prpt(parts))
    rect = bundle.report_header.elements[0]
    assert rect.kind == "rectangle"
    assert rect.style.bg_color == "#c9c98b"
    # no draw-shape / no border-width+style → the outline path draws
    # nothing; the fill is what must carry the visible bar
    assert rect.style.draw_shape is False
    assert rect.style.borders == {}


def test_rectangle_fill_renders_in_pdf_content_stream():
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            "<rectangle>"
            "<element-style>"
            '<border-styles background-color="#c9c98b"/>'
            '<content-styles scale="true" stroke-style="none"/>'
            '<spatial-styles x="0" y="0" min-width="100" min-height="20"/>'
            "</element-style>"
            "</rectangle>"
            "</root-level-content></report-header></r>"
        ),
    }
    data = _make_prpt(parts)
    pdf_bytes = NativeRenderer(lambda sql, params: [{}]).render(data, {})
    assert pdf_bytes[:4] == b"%PDF"
    content = PdfReader(io.BytesIO(pdf_bytes)).pages[0].get_contents().get_data()
    # #c9c98b == rgb(201, 201, 139) == (.788235, .788235, .545098) in 0-1
    # reportlab float notation (leading zero dropped)
    assert b".788235 .788235 .545098 rg" in content
    assert b" f" in content or b"f*" in content


def test_named_background_color_resolves():
    # "light_gray" appears in real bundles (underscore form; reportlab only
    # has "lightgrey") — must resolve, not silently no-op.
    from native.painter import parse_color

    assert parse_color("light_gray") is not None
    assert parse_color("white") == (1.0, 1.0, 1.0)
    assert parse_color("black") == (0.0, 0.0, 0.0)
    assert parse_color(None) is None
    assert parse_color("") is None
    assert parse_color("none") is None
    assert parse_color("not-a-real-color") is None


# ── multi-level (nested) group-body support ───────────────────
#
# A NESTED report replaces a group's <data-body> with a <group-body>
# wrapping exactly one more <group> (e.g. GL listings grouped by account
# then sub-account, per the task's example). Before this change,
# `_parse_group` raised UnsupportedFeature("group section 'group-body'").

def test_group_body_parses_nested_group_as_child():
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r>"
            '<group group-fields="acct">'
            "<group-header><root-level-content>"
            "<label><element-style>"
            '<spatial-styles x="0" y="0" min-width="50" min-height="10"/>'
            "</element-style><value>ACCT</value></label>"
            "</root-level-content></group-header>"
            "<group-body>"
            '<group group-fields="subacct">'
            "<group-header><root-level-content>"
            "<label><element-style>"
            '<spatial-styles x="0" y="0" min-width="50" min-height="10"/>'
            "</element-style><value>SUBACCT</value></label>"
            "</root-level-content></group-header>"
            "<data-body>"
            "<details><root-level-content>"
            '<text-field field="line"><element-style>'
            '<spatial-styles x="0" y="0" min-width="50" min-height="10"/>'
            "</element-style></text-field>"
            "</root-level-content></details>"
            "<no-data><root-level-content/></no-data>"
            "</data-body>"
            "<group-footer><root-level-content/></group-footer>"
            "</group>"
            "</group-body>"
            "<group-footer><root-level-content/></group-footer>"
            "</group>"
            "</r>"
        ),
    }
    bundle = PrptBundle.from_bytes(_make_prpt(parts))

    outer = bundle.group
    assert outer.fields == ["acct"]
    # the outer group is not a leaf: it carries no details/no_data of its own
    assert outer.details.elements == []
    assert outer.no_data.elements == []
    assert outer.child is not None

    inner = outer.child
    assert inner.fields == ["subacct"]
    assert inner.child is None  # leaf
    assert len(inner.details.elements) == 1
    assert inner.details.elements[0].field == "line"

    # has_data_bound_elements must walk the nested chain to find the leaf's
    # field binding, not just the outer (non-leaf) group's empty bands
    assert bundle.has_data_bound_elements() is True


def test_group_body_without_group_raises():
    # a group-body that (through malformed export or an unsupported nesting
    # shape) contains NO <group> child must raise, not silently leave
    # group.child = None — which would downgrade the group to an empty
    # leaf and silently drop its data rows (the Port-3 review finding).
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r>"
            '<group group-fields="acct">'
            "<group-header><root-level-content/></group-header>"
            "<group-body>"
            "<element-style/>"
            "</group-body>"
            "<group-footer><root-level-content/></group-footer>"
            "</group>"
            "</r>"
        ),
    }
    with pytest.raises(UnsupportedFeature, match="group-body without a nested group"):
        PrptBundle.from_bytes(_make_prpt(parts))


def test_group_body_with_unexpected_child_raises():
    # a genuinely unexpected structural child (not <group>, not the known-
    # ignorable element-style) must also raise rather than being silently
    # skipped.
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r>"
            '<group group-fields="acct">'
            "<group-header><root-level-content/></group-header>"
            "<group-body>"
            "<totally-unexpected-tag/>"
            "</group-body>"
            "<group-footer><root-level-content/></group-footer>"
            "</group>"
            "</r>"
        ),
    }
    with pytest.raises(UnsupportedFeature):
        PrptBundle.from_bytes(_make_prpt(parts))


def test_nested_group_emission_order():
    # drives NativeRenderer._emit_group directly against a FakeFlow that
    # just records (band, row) pairs, to prove the recursive break logic
    # emits bands in the exact interleaved order the Java engine would:
    # outer-header, inner-header, detail, inner-footer, (repeat per inner
    # partition), outer-footer, then the next outer partition.
    from native.model import Group
    from native.renderer import NativeRenderer

    inner = Group(fields=["b"])
    outer = Group(fields=["a"], child=inner)

    rows = [{"a": 1, "b": 1}, {"a": 1, "b": 2}, {"a": 2, "b": 1}]

    band_labels = {
        id(outer.header): "outer-header",
        id(outer.footer): "outer-footer",
        id(inner.header): "inner-header",
        id(inner.footer): "inner-footer",
        id(inner.details): "detail",
    }

    emitted = []

    class FakeFlow:
        def emit(self, band, row, subrenderer=None):
            emitted.append((band_labels[id(band)], dict(row)))

    renderer = NativeRenderer(lambda sql, params: [])
    renderer._emit_group(FakeFlow(), outer, rows, None)

    assert emitted == [
        ("outer-header", {"a": 1, "b": 1}),
        ("inner-header", {"a": 1, "b": 1}),
        ("detail", {"a": 1, "b": 1}),
        ("inner-footer", {"a": 1, "b": 1}),
        ("inner-header", {"a": 1, "b": 2}),
        ("detail", {"a": 1, "b": 2}),
        ("inner-footer", {"a": 1, "b": 2}),
        ("outer-footer", {"a": 1, "b": 2}),
        ("outer-header", {"a": 2, "b": 1}),
        ("inner-header", {"a": 2, "b": 1}),
        ("detail", {"a": 2, "b": 1}),
        ("inner-footer", {"a": 2, "b": 1}),
        ("outer-footer", {"a": 2, "b": 1}),
    ]


def test_leaf_top_level_group_unaffected_by_child_field():
    # a single-level report's group must still behave exactly as before:
    # child stays None, and _emit_group falls into the plain per-row loop.
    from native.model import Group
    from native.renderer import NativeRenderer

    leaf = Group(fields=["k"])
    assert leaf.child is None

    rows = [{"k": 1}, {"k": 1}, {"k": 2}]
    emitted = []

    class FakeFlow:
        def emit(self, band, row, subrenderer=None):
            label = {
                id(leaf.header): "header", id(leaf.footer): "footer",
                id(leaf.details): "detail",
            }[id(band)]
            emitted.append((label, dict(row)))

    NativeRenderer(lambda sql, params: [])._emit_group(FakeFlow(), leaf, rows, None)

    assert emitted == [
        ("header", {"k": 1}),
        ("detail", {"k": 1}),
        ("detail", {"k": 1}),
        ("footer", {"k": 1}),
        ("header", {"k": 2}),
        ("detail", {"k": 2}),
        ("footer", {"k": 2}),
    ]


def test_gl_listing_nested_group_renders_valid_pdf():
    # real-world 2-level group (gl_code > account_journal) sample: proves
    # the parser + recursive renderer produce a valid PDF end-to-end, not
    # just synthetic fixtures.
    from conftest import GL_LISTING_NESTED_PRPT

    if not GL_LISTING_NESTED_PRPT.exists():
        pytest.skip("sample_prpt/ corpus not present in this environment")

    from native.bundle import PrptBundle
    from native.renderer import NativeRenderer

    data = GL_LISTING_NESTED_PRPT.read_bytes()
    bundle = PrptBundle.from_bytes(data)  # must not raise UnsupportedFeature
    assert bundle.group.child is not None
    assert bundle.group.child.child is None  # exactly 2 levels

    rows = [
        {"gl_code": "1000", "gl_name": "Cash", "prev_balance": 1000.0,
         "account_journal": "AJ1", "account_date": "2026-01-01",
         "sum_acct_deb": 100.0, "sum_acct_cre": 0.0},
        {"gl_code": "1000", "gl_name": "Cash", "prev_balance": 1000.0,
         "account_journal": "AJ2", "account_date": "2026-01-02",
         "sum_acct_deb": 0.0, "sum_acct_cre": 50.0},
        {"gl_code": "2000", "gl_name": "AP", "prev_balance": 500.0,
         "account_journal": "AJ1", "account_date": "2026-01-03",
         "sum_acct_deb": 20.0, "sum_acct_cre": 0.0},
    ]

    def execute_query(sql, params):
        return rows

    params = {"date_from": "2026-01-01", "date_to": "2026-01-31", "code": "X"}
    pdf_bytes = NativeRenderer(execute_query).render(data, params)
    assert pdf_bytes[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1


def test_unknown_element_still_raises_unsupported_feature():
    # sanity check: ELEMENT_KINDS growing to include vertical-line/rectangle
    # must not have made the guard permissive for genuinely unknown kinds.
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            "<totally-unknown-kind>"
            "<element-style>"
            '<spatial-styles x="0" y="0" min-width="10" min-height="10"/>'
            "</element-style>"
            "</totally-unknown-kind>"
            "</root-level-content></report-header></r>"
        ),
    }
    with pytest.raises(UnsupportedFeature):
        PrptBundle.from_bytes(_make_prpt(parts))


# ── simple-barcodes (Port 4 FIX 2) ──────────────────────────

def _barcode_prpt_parts(tag: str = "sbarcodes:simple-barcodes", with_query: bool = True) -> dict:
    parts = {
        "styles.xml": "<r/>",
        "datadefinition.xml": (
            '<r><data-source report-query="Q"/></r>' if with_query else "<r/>"
        ),
        "layout.xml": (
            "<r><report-header><root-level-content>"
            '<%s field="reference" type="code128" '
            'xmlns:sbarcodes="http://reporting.pentaho.org/namespaces/engine/'
            'classic/extensions/sbarcodes/1.0">'
            "<element-style>"
            '<spatial-styles x="0" y="0" min-width="150" min-height="50"/>'
            "</element-style>"
            "</%s>"
            "</root-level-content></report-header></r>"
        ) % (tag, tag),
    }
    if with_query:
        # has_data_bound_elements() requires bundle.sql; a real query wires
        # the fetched rows through to the report-header's barcode element.
        parts["datasources/ds.xml"] = _sql_datasource_part("Q", "SELECT 'x' AS marker")
    return parts


def test_simple_barcodes_parses_field_and_type():
    bundle = PrptBundle.from_bytes(_make_prpt(_barcode_prpt_parts()))
    el = bundle.report_header.elements[0]
    assert el.kind == "simple-barcodes"
    assert el.field == "reference"
    assert el.barcode_type == "code128"
    assert el.style.width == 150
    assert el.style.height == 50


def test_simple_barcode_singular_spelling_parses():
    bundle = PrptBundle.from_bytes(_make_prpt(_barcode_prpt_parts("sbarcodes:simple-barcode")))
    el = bundle.report_header.elements[0]
    assert el.kind == "simple-barcode"
    assert el.barcode_type == "code128"


def test_simple_barcodes_renders_without_crashing():
    # end-to-end: a barcode element with a real bound value must not raise
    # during render and must produce a valid single-page PDF.
    data = _make_prpt(_barcode_prpt_parts())
    out = NativeRenderer(lambda sql, params: [{"reference": "ABC123"}]).render(data, {})
    assert out.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) == 1


def test_simple_barcodes_empty_value_does_not_crash():
    data = _make_prpt(_barcode_prpt_parts())
    # execute_query returns no rows → report-header still emits once with
    # row={} (see NativeRenderer._emit_report), so el.field "reference"
    # resolves to None — draw_barcode must skip silently, not raise.
    out = NativeRenderer(lambda sql, params: []).render(data, {})
    assert out.startswith(b"%PDF")


def test_barcode_render_on_real_corpus_sample():
    # real-world sample (frpic_v16__product_barcode.prpt): a code128
    # <sbarcodes:simple-barcodes core:field="barcode" type="code128"> label
    # sheet — proves the fix against an actual export, not just a synthetic
    # fixture.
    from conftest import BARCODE_PRPT

    if not BARCODE_PRPT.exists():
        pytest.skip("sample_prpt/ corpus not present in this environment")

    rows = [
        {"barcode": "4801234567890", "note": "Fragile", "product": "Widget",
         "serial": "SN-0001"},
        {"barcode": "4801234567891", "note": "", "product": "Gadget",
         "serial": "SN-0002"},
    ]
    out = NativeRenderer(lambda sql, params: rows).render(
        BARCODE_PRPT.read_bytes(), {"ids": [1, 2]}
    )
    assert out.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) >= 1
