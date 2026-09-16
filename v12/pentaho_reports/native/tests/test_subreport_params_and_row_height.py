"""Sub-report parameter mapping and percentage-height detail rows.

Both shapes come from real NextAsia Land bundles:

* ap_voucher.prpt's journal-line sub-report declares
  ``<input-parameter name="id" alias="id"/>`` and queries ``${id}``;
  tk_prs_form.prpt maps ``id`` to ``ids``; check_voucher.prpt imports
  everything with ``name="*"``.
* tk_request_for_quotation.prpt's details band has no height of its own:
  every cell is ``min-height="100%"`` + ``dynamic-height="true"``, so the
  row is as tall as its tallest wrapped cell.
"""
import io
import zipfile

from pypdf import PdfReader
from reportlab.pdfgen import canvas as rl_canvas

from native.bundle import PrptBundle
from native.painter import Painter
from native.renderer import NativeRenderer, _band_height


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


def _text_field(field, x=0, y=0, width=200, height="12", extra_styles=""):
    return (
        '<text-field field="%s"><element-style>'
        '<spatial-styles x="%s" y="%s" min-width="%s" min-height="%s"/>%s'
        "</element-style></text-field>" % (field, x, y, width, height, extra_styles)
    )


def _details_layout(content: str) -> str:
    return (
        "<r><group><data-body><details><root-level-content>%s"
        "</root-level-content></details></data-body></group></r>" % content
    )


def _master_with_subreport(mapping_xml: str, sub_sql: str, sub_field: str) -> bytes:
    """Master report: one details row per master record, each embedding a sub-report."""
    return _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": '<r><data-source report-query="Master"/></r>',
        "datasources/ds.xml": _sql_datasource_part(
            "Master", "SELECT id, name FROM master WHERE id IN (${ids})"),
        "layout.xml": _details_layout(
            _text_field("name")
            + '<sub-report href="/subreport/content.xml"><element-style>'
              '<spatial-styles x="0" y="14" min-width="200" min-height="12"/>'
              "</element-style></sub-report>"),
        "subreport/styles.xml": "<r/>",
        "subreport/datadefinition.xml": (
            "<r>%s<data-source report-query=\"Lines\"/></r>" % mapping_xml),
        "subreport/datasources/ds.xml": _sql_datasource_part("Lines", sub_sql),
        "subreport/layout.xml": _details_layout(_text_field(sub_field)),
    })


def _pdf_text(data: bytes) -> str:
    assert data.startswith(b"%PDF")
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


MASTER_ROWS = [{"id": 7, "name": "Bill Seven"}, {"id": 8, "name": "Bill Eight"}]


# ── sub-report parameter mapping ─────────────────────────────

def test_input_parameter_mapping_is_parsed():
    prpt = _master_with_subreport(
        '<parameter-mapping><input-parameter name="id" alias="ids"/>'
        '<input-parameter name="*" alias="*"/></parameter-mapping>',
        "SELECT 1", "line")
    sub = PrptBundle.from_bytes(prpt).group.details.elements[1].subreport
    assert sub.input_mappings == [("id", "ids"), ("*", "*")]


def test_subreport_receives_master_row_field_per_row():
    # ap_voucher.prpt shape: name="id" alias="id", sub-report SQL uses ${id}
    prpt = _master_with_subreport(
        '<parameter-mapping><input-parameter name="id" alias="id"/></parameter-mapping>',
        "SELECT line FROM lines WHERE move_id = (${id})", "line")
    sub_params = []

    def execute_query(sql, params):
        if "FROM lines" in sql:
            sub_params.append(list(params))
            return [{"line": "line-of-%s" % params[0]}]
        return [dict(r) for r in MASTER_ROWS]

    text = _pdf_text(NativeRenderer(execute_query).render(prpt, {"ids": [7, 8]}))
    assert "line-of-7" in text
    assert "line-of-8" in text
    # each master row runs the sub-report query with its own id (the
    # measure and paint passes share one cached result per parameter set)
    assert sorted(set(map(tuple, sub_params))) == [(7,), (8,)]


def test_subreport_alias_overrides_reserved_parameter():
    # tk_prs_form.prpt shape: master "id" is passed in as the sub-report's
    # "ids" — it must not see the top-level multi-record ids list
    prpt = _master_with_subreport(
        '<parameter-mapping><input-parameter name="id" alias="ids"/></parameter-mapping>',
        "SELECT line FROM lines WHERE req_id IN (${ids})", "line")
    sub_params = []

    def execute_query(sql, params):
        if "FROM lines" in sql:
            sub_params.append(list(params))
            return [{"line": "lines-for-%s" % ",".join(map(str, params))}]
        return [dict(r) for r in MASTER_ROWS]

    text = _pdf_text(NativeRenderer(execute_query).render(prpt, {"ids": [7, 8]}))
    assert "lines-for-7" in text and "lines-for-8" in text
    assert "lines-for-7,8" not in text
    assert all(len(p) == 1 for p in sub_params)


def test_subreport_wildcard_imports_master_fields():
    # check_voucher.prpt shape: name="*" alias="*"
    prpt = _master_with_subreport(
        '<parameter-mapping><input-parameter name="*" alias="*"/></parameter-mapping>',
        "SELECT label FROM lines WHERE partner = ${name} AND move_id IN (${ids})", "label")

    def execute_query(sql, params):
        if "FROM lines" in sql:
            return [{"label": "%s/%s" % (params[0], params[1])}]
        return [dict(r) for r in MASTER_ROWS]

    text = _pdf_text(NativeRenderer(execute_query).render(prpt, {"ids": [7, 8]}))
    # ${name} comes from the master row; ${ids} is still the reserved list
    assert "Bill Seven/7" in text
    assert "Bill Eight/7" in text


def test_subreport_mapping_with_unknown_source_passes_null():
    prpt = _master_with_subreport(
        '<parameter-mapping><input-parameter name="partner_id" alias="partner_id"/>'
        "</parameter-mapping>",
        "SELECT line FROM lines WHERE partner_id = ${partner_id}", "line")
    seen = []

    def execute_query(sql, params):
        if "FROM lines" in sql:
            seen.append(list(params))
            return []
        return [dict(r) for r in MASTER_ROWS]

    NativeRenderer(execute_query).render(prpt, {"ids": [7, 8]})  # no KeyError
    assert seen and all(p == [None] for p in seen)


def test_subreport_without_mapping_keeps_top_level_parameters():
    prpt = _master_with_subreport("", "SELECT line FROM lines WHERE move_id IN (${ids})", "line")
    seen = []

    def execute_query(sql, params):
        if "FROM lines" in sql:
            seen.append(list(params))
            return [{"line": "shared"}]
        return [dict(r) for r in MASTER_ROWS]

    NativeRenderer(execute_query).render(prpt, {"ids": [7, 8]})
    assert seen and all(p == [7, 8] for p in seen)


# ── percentage-height, dynamic-height detail rows ────────────

PCT_CELL_STYLES = (
    '<border-styles padding-top="5" padding-bottom="5"/>'
    '<content-styles dynamic-height="true"/>'
)


def _pct_row_prpt() -> bytes:
    cells = (
        _text_field("product", x=0, width=80, height="100%", extra_styles=PCT_CELL_STYLES)
        + _text_field("qty", x=80, width=40, height="100%", extra_styles=PCT_CELL_STYLES)
    )
    return _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": '<r><data-source report-query="Lines"/></r>',
        "datasources/ds.xml": _sql_datasource_part("Lines", "SELECT product, qty FROM l"),
        "layout.xml": _details_layout(cells),
    })


def _painter():
    return Painter(rl_canvas.Canvas(io.BytesIO(), pagesize=(612, 792)), 792)


def test_dynamic_percent_height_cells_give_the_row_a_height():
    details = PrptBundle.from_bytes(_pct_row_prpt()).group.details
    short = _band_height(details, _painter(), {"product": "Door knob", "qty": "2"})
    assert short > 10  # one text line + 5pt top/bottom padding, not 0
    long_row = {"product": "A very long product description that wraps " * 3, "qty": "2"}
    assert _band_height(details, _painter(), long_row) > short


def test_non_dynamic_percent_height_cell_still_contributes_nothing():
    prpt = _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": _details_layout(_text_field("product", height="100%")),
    })
    details = PrptBundle.from_bytes(prpt).group.details
    assert _band_height(details, _painter(), {"product": "Door knob"}) == 0.0


def test_percent_height_rows_do_not_overlap():
    rows = [{"product": "ROW-ONE", "qty": "1"}, {"product": "ROW-TWO", "qty": "2"},
            {"product": "ROW-THREE", "qty": "3"}]
    out = NativeRenderer(lambda sql, params: [dict(r) for r in rows]).render(
        _pct_row_prpt(), {"ids": [1]})

    ys = {}

    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip().startswith("ROW-"):
            ys[text.strip()] = tm[5]

    PdfReader(io.BytesIO(out)).pages[0].extract_text(visitor_text=visitor)
    assert set(ys) == {"ROW-ONE", "ROW-TWO", "ROW-THREE"}
    # PDF y grows upwards: each row sits strictly below the previous one
    assert ys["ROW-ONE"] > ys["ROW-TWO"] > ys["ROW-THREE"]


# ── details header/footer, watermark, empty report ───────────
#
# Benchmarked against the Java engine on the same database:
# tk_purchase_order_form.prpt prints "** Nothing Follows **" and GRAND TOTAL
# from <details-footer>; delivery_receipt_owner.prpt draws its whole line
# grid and signature block in the <watermark> band; check_voucher.prpt with
# no matching record comes back from Java as one blank page.

def _label(text, x=0, y=0, width=200, height=12):
    return (
        '<label><element-style><spatial-styles x="%s" y="%s" min-width="%s" min-height="%s"/>'
        "</element-style><value>%s</value></label>" % (x, y, width, height, text)
    )


def _prpt_with_detail_bands(details_header="", details_footer="", watermark="", wrapped=False):
    # Report Designer writes details-header/footer elements directly under
    # the section tag; `wrapped` exercises the <root-level-content> form too
    wrap = (lambda s: "<root-level-content>%s</root-level-content>" % s) if wrapped else (lambda s: s)
    return _make_prpt({
        "styles.xml": "<r><watermark>%s</watermark></r>" % watermark,
        "datadefinition.xml": '<r><data-source report-query="Lines"/></r>',
        "datasources/ds.xml": _sql_datasource_part("Lines", "SELECT product FROM l"),
        "layout.xml": (
            "<r><group><data-body>"
            "<details-header>%s</details-header>"
            "<details><root-level-content>%s</root-level-content></details>"
            "<details-footer>%s</details-footer>"
            "</data-body></group></r>"
            % (wrap(details_header), _text_field("product"), wrap(details_footer))
        ),
    })


def test_details_header_and_footer_are_parsed():
    for wrapped in (False, True):
        prpt = _prpt_with_detail_bands(_label("QTY HEADER"), _text_field("grand_total"), wrapped=wrapped)
        group = PrptBundle.from_bytes(prpt).group
        assert group.details_header.elements[0].value == "QTY HEADER"
        assert group.details_footer.elements[0].field == "grand_total"


def test_details_footer_prints_once_after_the_rows():
    rows = [{"product": "LINE-A", "grand_total": "99.00"}, {"product": "LINE-B", "grand_total": "99.00"}]
    prpt = _prpt_with_detail_bands(_label("ITEMS"), _label("** Nothing Follows **")
                                   + _text_field("grand_total", y=12))
    out = NativeRenderer(lambda sql, params: [dict(r) for r in rows]).render(prpt, {"ids": [1]})
    text = _pdf_text(out)
    assert text.count("ITEMS") == 1
    assert text.count("Nothing Follows") == 1
    assert text.count("99.00") == 1
    assert text.index("ITEMS") < text.index("LINE-A") < text.index("LINE-B") < text.index("Nothing Follows")


def test_details_header_and_footer_skip_when_no_rows():
    prpt = _prpt_with_detail_bands(_label("ITEMS"), _label("Nothing Follows"))
    text = _pdf_text(NativeRenderer(lambda sql, params: []).render(prpt, {"ids": [1]}))
    assert "ITEMS" not in text and "Nothing Follows" not in text


def test_watermark_band_is_painted_on_every_page():
    rows = [{"product": "LINE-%03d" % i} for i in range(120)]  # 12pt rows → 2 letter pages
    prpt = _prpt_with_detail_bands(watermark=_label("PARTICULARS", y=0))
    reader = PdfReader(io.BytesIO(NativeRenderer(lambda sql, params: [dict(r) for r in rows]).render(
        prpt, {"ids": [1]})))
    assert len(reader.pages) >= 2
    assert all("PARTICULARS" in p.extract_text() for p in reader.pages)


def test_watermark_is_painted_when_the_query_returns_nothing():
    prpt = _prpt_with_detail_bands(watermark=_label("SIGNATURE OVER PRINTED NAME"))
    text = _pdf_text(NativeRenderer(lambda sql, params: []).render(prpt, {"ids": [1]}))
    assert "SIGNATURE OVER PRINTED NAME" in text


def test_report_with_nothing_to_draw_is_one_blank_page():
    prpt = _prpt_with_detail_bands()
    out = NativeRenderer(lambda sql, params: []).render(prpt, {"ids": [0]})
    assert len(PdfReader(io.BytesIO(out)).pages) == 1


# ── fonts, visibility, text-field numbers (Java engine parity) ──
#
# The Java engine writes "Arial" as the base-14 Helvetica (not embedded) and
# inherits text styles from the enclosing band; ap_voucher.prpt hides its
# signature band and "Bill Due" with visible="false"; tk_stock_move.prpt's
# quantity is a text-field whose numeric(…,2) value Java prints as "2.00".

def _band_prpt(band_style, elements):
    return _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-header><root-level-content>"
            "<element-style>%s</element-style>%s"
            "</root-level-content></report-header></r>" % (band_style, elements)
        ),
    })


def _pdf_fonts(data: bytes) -> set:
    fonts = set()
    for page in PdfReader(io.BytesIO(data)).pages:
        for font in page["/Resources"]["/Font"].values():
            fonts.add(str(font.get_object()["/BaseFont"]))
    return fonts


def test_arial_renders_as_base14_helvetica_like_the_java_engine():
    from native import fonts
    assert fonts.resolve("Arial") == "Helvetica"
    assert fonts.resolve("Arial", bold=True) == "Helvetica-Bold"
    out = NativeRenderer(lambda sql, params: []).render(
        _band_prpt('<text-styles font-face="Arial"/>', _label("Hello")), {"ids": [1]})
    assert _pdf_fonts(out) == {"/Helvetica"}


def test_elements_inherit_text_styles_from_their_band():
    prpt = _band_prpt(
        '<text-styles font-face="Arial" font-size="8" bold="true"/>',
        _label("inherits")
        + '<label><element-style><spatial-styles x="0" y="20" min-width="200" min-height="12"/>'
          '<text-styles bold="false" font-size="12"/></element-style><value>overrides</value></label>')
    band = PrptBundle.from_bytes(prpt).report_header
    inherits, overrides = band.elements
    assert (inherits.style.font_face, inherits.style.font_size, inherits.style.bold) == ("Arial", 8.0, True)
    assert (overrides.style.font_face, overrides.style.font_size, overrides.style.bold) == ("Arial", 12.0, False)


def test_nested_band_passes_inherited_font_down():
    prpt = _band_prpt(
        '<text-styles font-face="Arial"/>',
        "<band><element-style><spatial-styles x='0' y='0' min-width='200' min-height='20'/>"
        "</element-style>%s</band>" % _label("deep"))
    deep = PrptBundle.from_bytes(prpt).report_header.elements[0].elements[0]
    assert deep.style.font_face == "Arial"


def test_invisible_elements_and_bands_are_not_drawn_and_take_no_space():
    hidden_label = (
        '<label><element-style><common-styles visible="false"/>'
        '<spatial-styles x="0" y="40" min-width="200" min-height="12"/></element-style>'
        "<value>Bill Due</value></label>")
    hidden_band = (
        "<band><element-style><common-styles visible=\"false\"/>"
        '<spatial-styles x="0" y="60" min-width="200" min-height="40"/></element-style>'
        "%s</band>" % _label("Verified By:"))
    prpt = _band_prpt("", _label("Shown") + hidden_label + hidden_band)
    band = PrptBundle.from_bytes(prpt).report_header
    assert _band_height(band, _painter(), {}) == 12.0
    text = _pdf_text(NativeRenderer(lambda sql, params: []).render(prpt, {"ids": [1]}))
    assert "Shown" in text
    assert "Bill Due" not in text and "Verified By" not in text


def test_text_field_prints_numbers_like_java_string_value():
    from decimal import Decimal
    from native.formats import format_text_value
    assert format_text_value(Decimal("2.00")) == "2.00"
    assert format_text_value(Decimal("1234.5")) == "1234.5"
    assert format_text_value(7) == "7"
    assert format_text_value(2.0) == "2.0"
    assert format_text_value(12345678.0) == "1.2345678E7"
    assert format_text_value("already text") == "already text"
    assert format_text_value(None) == ""


def test_text_field_numeric_value_keeps_database_scale():
    from decimal import Decimal
    prpt = _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": '<r><data-source report-query="Moves"/></r>',
        "datasources/ds.xml": _sql_datasource_part("Moves", "SELECT quantity FROM stock_move"),
        "layout.xml": _details_layout(_text_field("quantity")),
    })
    out = NativeRenderer(lambda sql, params: [{"quantity": Decimal("2.00")}]).render(prpt, {"ids": [1]})
    assert "2.00" in _pdf_text(out)


# ── inline band layout (ap_voucher.prpt "Bill Total : Php 90.00") ──

def _inline_total_prpt(alignment="right"):
    band = (
        "<band><element-style>"
        '<band-styles layout="inline"/><border-styles padding-right="5"/>'
        '<common-styles alignment="%s"/>'
        '<spatial-styles x="0" y="0" min-width="100%%" min-height="20"/>'
        '<text-styles font-face="Arial" font-size="10"/>'
        "</element-style>"
        '<label><element-style><spatial-styles min-height="20"/><text-styles bold="true"/>'
        "</element-style><value>Bill Total : Php </value></label>"
        '<number-field field="total" format-string="#,##0.00;(#,##0.00)"><element-style>'
        '<spatial-styles min-height="20"/><text-styles bold="true"/></element-style></number-field>'
        "</band>" % alignment
    )
    return _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": '<r><data-source report-query="Bill"/></r>',
        "datasources/ds.xml": _sql_datasource_part("Bill", "SELECT total FROM bill"),
        "layout.xml": "<r><report-footer><root-level-content>%s</root-level-content></report-footer></r>" % band,
    })


def _text_runs(data: bytes):
    runs = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip():
            runs.append((text.strip(), tm[4], tm[5]))

    PdfReader(io.BytesIO(data)).pages[0].extract_text(visitor_text=visitor)
    return runs


def test_percent_min_width_is_parsed():
    band_el = PrptBundle.from_bytes(_inline_total_prpt()).report_footer.elements[0]
    assert band_el.style.layout == "inline"
    assert band_el.style.width_pct == 100.0


def test_inline_band_lays_children_out_on_one_right_aligned_line():
    out = NativeRenderer(lambda sql, params: [{"total": 90}]).render(_inline_total_prpt(), {"ids": [1]})
    text = _pdf_text(out)
    assert "Bill Total : Php" in text and "90.00" in text
    runs = dict((t, (x, y)) for t, x, y in _text_runs(out))
    label_x, label_y = runs["Bill Total : Php"]
    total_x, total_y = runs["90.00"]
    assert label_y == total_y                 # one line, not one character per line
    assert label_x < total_x                  # label first, amount after it
    assert total_x > 612 - 5 - 40             # pushed against the right edge (letter, no margins)


def test_inline_band_left_alignment_starts_at_the_band_origin():
    out = NativeRenderer(lambda sql, params: [{"total": 90}]).render(
        _inline_total_prpt("left"), {"ids": [1]})
    runs = dict((t, (x, y)) for t, x, y in _text_runs(out))
    assert runs["Bill Total : Php"][0] < 5


def test_row_band_places_children_side_by_side_by_their_widths():
    # ap_voucher.prpt journal-line header: layout="row", labels carry only
    # min-width (Analytic even has a stale x the row layout ignores)
    labels = "".join(
        '<label><element-style><spatial-styles %s min-width="%s" min-height="20"/></element-style>'
        "<value>%s</value></label>" % (extra, w, text)
        for text, w, extra in [("Acct", 104, ""), ("Account", 180, ""), ("Debit", 70, ""),
                               ("Analytic", 145, 'x="400" y="0"')])
    band = ("<band><element-style><band-styles layout=\"row\"/>"
            '<spatial-styles min-width="100%%" min-height="20"/></element-style>%s</band>' % labels)
    out = NativeRenderer(lambda sql, params: []).render(_band_prpt("", band), {"ids": [1]})
    xs = dict((t, x) for t, x, _y in _text_runs(out))
    assert xs["Acct"] < 5
    assert abs(xs["Account"] - 104) < 1
    assert abs(xs["Debit"] - 284) < 1
    assert abs(xs["Analytic"] - 354) < 1


# ── sub-report placement + style formulas (tk_prs_form.prpt signatures) ──
#
# The department-head signature sub-report element has no placement of its
# own; the Java engine places it by the sub-report's root style (y=12), which
# lines its signature line up with the footer's budget/COO/CEO lines. The CEO
# line's border style is a formula: IF(ISBLANK([ceo]); "none"; "solid"), and
# the query returns '' (not NULL) for an unsigned PRS, so Java draws it.

def _footer_with_unplaced_subreport(root_y="12"):
    return _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": "<r/>",
        "layout.xml": (
            "<r><report-footer><root-level-content>"
            '<sub-report href="/subreport/content.xml"/>'
            "</root-level-content></report-footer></r>"),
        "subreport/styles.xml": "<r/>",
        "subreport/datadefinition.xml": "<r/>",
        "subreport/layout.xml": (
            '<r><element-style><spatial-styles x="4" y="%s" min-width="100" min-height="20"/>'
            "</element-style></r>" % root_y),
    })


def test_unplaced_subreport_uses_its_root_style_position():
    sub_el = PrptBundle.from_bytes(_footer_with_unplaced_subreport()).report_footer.elements[0]
    assert (sub_el.style.x, sub_el.style.y) == (4.0, 12.0)


def test_placed_subreport_keeps_its_own_y():
    prpt = _master_with_subreport("", "SELECT 1", "line")  # element has spatial-styles y=14
    sub_el = PrptBundle.from_bytes(prpt).group.details.elements[1]
    assert sub_el.style.y == 14.0


def test_formula_evaluator():
    from native.formula import FormulaError, evaluate
    blank = '=IF(ISBLANK([ceo]); "none"; "solid")'
    assert evaluate(blank, {"ceo": None}) == "none"
    assert evaluate(blank, {"ceo": ""}) == "solid"        # '' is not blank in Pentaho
    assert evaluate(blank, {"ceo": "Juan"}) == "solid"
    payee = '=IF([payee]="";"false";"true")'
    assert evaluate(payee, {"payee": ""}) == "false"
    assert evaluate(payee, {"payee": None}) == "false"
    assert evaluate(payee, {"payee": "ACME"}) == "true"
    assert evaluate('=IF(AND(NOT([a]="x"), [b]<>""), "y", "n")', {"a": "z", "b": "q"}) == "y"
    import pytest
    with pytest.raises(FormulaError):
        evaluate("=SUMIF([a]; 1)", {"a": 1})


def _label_with_formula(expression_xml, border_xml='<border-styles border-top-width="0.5"/>'):
    return _make_prpt({
        "styles.xml": "<r/>",
        "datadefinition.xml": '<r><data-source report-query="Q"/></r>',
        "datasources/ds.xml": _sql_datasource_part("Q", "SELECT ceo, payee FROM prs"),
        "layout.xml": (
            "<r><report-header><root-level-content>"
            '<text-field field="ceo"><element-style>%s'
            '<spatial-styles x="0" y="0" min-width="120" min-height="20"/></element-style>%s</text-field>'
            '<label><element-style><spatial-styles x="0" y="30" min-width="120" min-height="20"/>'
            '</element-style><value>PAYEE</value>'
            '<style-expression style-key="visible" formula="=IF([payee]=&quot;&quot;;&quot;false&quot;;&quot;true&quot;)"/>'
            "</label></root-level-content></report-header></r>" % (border_xml, expression_xml)),
    })


CEO_BORDER = ('<style-expression style-key="border-top-style" '
              'formula="=IF(ISBLANK([ceo]); &quot;none&quot;; &quot;solid&quot;)"/>')


def _draws_line(out: bytes) -> bool:
    content = PdfReader(io.BytesIO(out)).pages[0].get_contents().get_data()
    return b" l" in content or b"\nl" in content


def test_border_style_formula_draws_line_for_empty_string():
    prpt = _label_with_formula(CEO_BORDER)
    el = PrptBundle.from_bytes(prpt).report_header.elements[0]
    assert el.style_expressions == [("border-top-style", '=IF(ISBLANK([ceo]); "none"; "solid")')]
    assert _draws_line(NativeRenderer(lambda s, p: [{"ceo": "", "payee": "X"}]).render(prpt, {"ids": [1]}))
    assert not _draws_line(NativeRenderer(lambda s, p: [{"ceo": None, "payee": "X"}]).render(prpt, {"ids": [1]}))


def test_visible_formula_hides_element_per_row():
    prpt = _label_with_formula("")
    assert "PAYEE" in _pdf_text(NativeRenderer(lambda s, p: [{"ceo": "a", "payee": "ACME"}]).render(prpt, {"ids": [1]}))
    assert "PAYEE" not in _pdf_text(NativeRenderer(lambda s, p: [{"ceo": "a", "payee": ""}]).render(prpt, {"ids": [1]}))
