"""Geometry fidelity vs the Java engine, via the calibration probe grid.

Expected positions are computed from the closed-form model fitted against a
reference Java Pentaho render of the same probes (see calibration.py docstring).
If these tests pass, native text sits within ~0.2pt of the Java engine.
"""
import pytest

import calibration as cal
from calibration import MARGIN, PROBES, build_prpt, pdf_text_items, probe_lines

from native import fonts
from native.painter import Painter, max_ascent, wrap_text
from native.renderer import NativeRenderer

TOL = 0.2


@pytest.fixture(scope="module")
def rendered():
    pdf = NativeRenderer(lambda sql, params: []).render(build_prpt(), {"ids": [1]})
    return pdf_text_items(pdf)


def _font_of(o):
    face = None if o.get("serif") else "Arial"
    return fonts.resolve(face, o.get("bold", False), False), float(o.get("size", 10))


def expected_baselines(probe):
    """The fitted Java model (independent of painter.draw_text internals)."""
    text, x, y, w, h, o = probe
    font, size = _font_of(o)
    inset_t = o.get("pad_t", 0) + o.get("bt", 0) + o.get("box", 0)
    inset_b = o.get("pad_b", 0) + o.get("bb", 0) + o.get("box", 0)
    inset_l = o.get("pad_l", 0) + o.get("box", 0)
    inset_r = o.get("pad_r", 0) + o.get("box", 0)
    lines = wrap_text(text, font, size, w - inset_l - inset_r)
    n = len(lines)
    top = MARGIN + y + inset_t
    bottom = MARGIN + y + h - inset_b
    block_h = n * size
    valign = o.get("valign", "top")
    if valign == "middle":
        block_top = max(top, (top + bottom) / 2.0 - block_h / 2.0)
    elif valign == "bottom":
        block_top = max(top, bottom - inset_b - block_h)
    else:
        block_top = top
    asc = max_ascent(font, size)
    return [block_top + asc + i * size for i in range(n)], MARGIN + x + inset_l


def test_max_ascent_matches_reference_constants():
    # ground truth measured from the Java engine calibration render
    assert max_ascent(fonts.resolve("Arial", False, False), 10) == pytest.approx(10.06, abs=0.02)
    assert max_ascent(fonts.resolve("Arial", True, False), 10) == pytest.approx(10.10, abs=0.02)
    assert max_ascent(fonts.resolve("Arial", True, False), 16) == pytest.approx(16.16, abs=0.03)
    assert max_ascent(fonts.resolve("Arial", False, False), 8) == pytest.approx(8.05, abs=0.02)
    assert max_ascent(fonts.resolve(None, False, False), 10) == pytest.approx(8.98, abs=0.02)


@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p[0].split()[0])
def test_probe_baselines_match_java_model(rendered, probe):
    want_y, want_x = expected_baselines(probe)
    got = probe_lines(rendered, probe)
    assert len(got) == len(want_y), "line count for %s: got %r" % (probe[0], got)
    for (gy, gx, _s), wy in zip(got, want_y):
        assert gy == pytest.approx(wy, abs=TOL)
    # left-aligned text starts at x + left inset
    assert got[0][1] == pytest.approx(want_x, abs=TOL)


def test_line_advance_is_font_size(rendered):
    w1 = [p for p in PROBES if p[0].startswith("W1")][0]
    got = probe_lines(rendered, w1)
    assert len(got) >= 3
    for (a, _xa, _sa), (b, _xb, _sb) in zip(got, got[1:]):
        assert b - a == pytest.approx(10.0, abs=0.05)
    w3 = [p for p in PROBES if p[0].startswith("W3")][0]
    got8 = probe_lines(rendered, w3)
    for (a, _xa, _sa), (b, _xb, _sb) in zip(got8, got8[1:]):
        assert b - a == pytest.approx(8.0, abs=0.05)


@pytest.mark.skipif(not fonts.resolve("Arial", False, False).startswith("Prpt"),
                    reason="real Arial not available; wrap points may differ")
def test_wrap_counts_match_reference(rendered):
    # observed in the Java engine calibration render with real Arial
    counts = {"W1": 4, "W2": 4, "W3": 3, "W4": 4}
    for probe in PROBES:
        pid = probe[0].split()[0]
        if pid in counts:
            assert len(probe_lines(rendered, probe)) == counts[pid], pid


def test_image_left_middle_anchor(tmp_path):
    # content-field with alignment=left / valign=middle must hug the left edge,
    # vertically centered (Java engine: 179x88 logo in 184.794x55 box -> x=box left)
    import io as _io
    from PIL import Image
    from reportlab.pdfgen import canvas as rl_canvas

    from native.model import Style

    png = _io.BytesIO()
    Image.new("RGB", (179, 88), "white").save(png, format="PNG")

    buf = _io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    painter = Painter(c, 792.0)
    style = Style(align="left", valign="middle", scale=True, keep_aspect=True)
    painter.draw_image((40.0, 40.0, 184.794, 55.0), png.getvalue(), style)
    c.showPage()
    c.save()

    placements = cal.pdf_image_placements(buf.getvalue())
    assert placements, "image was not drawn"
    im = placements[0]
    assert im["x"] == pytest.approx(40.0, abs=0.1)          # left edge, not centered
    assert im["w"] == pytest.approx(111.9, abs=0.2)         # 179x88 scaled to fit h=55
    assert im["h"] == pytest.approx(55.0, abs=0.1)
    assert im["y_top"] == pytest.approx(40.0, abs=0.1)      # fills box height -> top edge


def _mini_prpt(styles_header_xml):
    """A one-off bundle with the given page-header content."""
    import io as _io
    import zipfile

    styles = """<?xml version="1.0" encoding="UTF-8"?>
<style xmlns="http://reporting.pentaho.org/namespaces/engine/classic/bundle/style/1.0" xmlns:layout="http://reporting.pentaho.org/namespaces/engine/classic/bundle/layout/1.0" xmlns:core="http://reporting.pentaho.org/namespaces/engine/attributes/core">
  <page-definition pageformat="LETTER" orientation="portrait" margin-top="40" margin-left="40" margin-bottom="40" margin-right="40"/>
  <layout:page-header>%s</layout:page-header>
  <layout:page-footer></layout:page-footer>
</style>""" % styles_header_xml
    layout = """<?xml version="1.0" encoding="UTF-8"?>
<layout xmlns="http://reporting.pentaho.org/namespaces/engine/classic/bundle/layout/1.0" xmlns:core="http://reporting.pentaho.org/namespaces/engine/attributes/core">
  <report-header><root-level-content/></report-header>
  <group core:group-fields=""><fields/>
    <group-header><root-level-content/></group-header>
    <data-body><details><root-level-content/></details><no-data><root-level-content/></no-data></data-body>
    <group-footer><root-level-content/></group-footer>
  </group>
  <report-footer><root-level-content/></report-footer>
</layout>"""
    datadef = ('<?xml version="1.0" encoding="UTF-8"?><data-definition '
               'xmlns="http://reporting.pentaho.org/namespaces/engine/classic/bundle/data/1.0"/>')
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("styles.xml", styles)
        zf.writestr("layout.xml", layout)
        zf.writestr("datadefinition.xml", datadef)
    return buf.getvalue()


def test_band_border_insets_children():
    # a nested band's border shifts its children inward by the border width
    # (observed on the sales invoice: 2pt frame band -> child at y+2/x+2)
    header = """
    <layout:band>
      <element-style>
        <border-styles border-width="2" border-style="solid"/>
        <spatial-styles x="0" y="0" min-width="300" min-height="60"/>
      </element-style>
      <layout:label>
        <element-style>
          <common-styles alignment="left" vertical-alignment="top"/>
          <spatial-styles x="10" y="20" min-width="200" min-height="18"/>
          <text-styles font-face="Arial"/>
        </element-style>
        <core:value>BANDCHILD probe</core:value>
      </layout:label>
    </layout:band>"""
    pdf = NativeRenderer(lambda sql, params: []).render(_mini_prpt(header), {"ids": [1]})
    items = [it for it in pdf_text_items(pdf) if it[2].startswith("BANDCHILD")]
    assert items, "band child did not render"
    x, y, _s = items[0]
    font = fonts.resolve("Arial", False, False)
    # margin 40 + band border 2 + child x/y; baseline = top + asc
    assert x == pytest.approx(40 + 2 + 10, abs=TOL)
    assert y == pytest.approx(40 + 2 + 20 + max_ascent(font, 10), abs=TOL)


def test_subreport_root_x_offset_applied():
    # the Java engine indents a banded sub-report by its root layout x
    # (delivery receipt: x=12.575) while y stays flow-positioned
    from conftest import DELIVERY_RECEIPT_PRPT

    from native.bundle import PrptBundle

    bundle = PrptBundle.from_bytes(DELIVERY_RECEIPT_PRPT.read_bytes())
    subs = [el for el in bundle.report_footer.elements if el.kind == "sub-report"]
    assert subs, "delivery receipt report footer has a sub-report"
    assert subs[0].style.x == pytest.approx(12.575)
    assert subs[0].style.y == 0.0
