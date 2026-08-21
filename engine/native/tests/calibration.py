"""Calibration probes: geometry fixtures fitted against the Java engine.

The probe grid below was rendered through the reference Java Pentaho engine
(2026-08-07, engine 5.0-SNAPSHOT, macOS Arial/Times) and the resulting text
baselines fitted to a closed-form model — see test_calibration.py.  The fitted
Java model is:

    asc(font, size)  = bbox_yMax(font) / 1000 * size     (font bounding box)
    advance          = size                               (no leading)
    inset(side)      = padding[side] + border[side].width
    content_top      = y + inset(top)
    content_bottom   = y + h - inset(bottom)
    block_h          = n_lines * size
    top:    block_top = content_top
    middle: block_top = max(content_top, mid(content) - block_h / 2)
    bottom: block_top = max(content_top,
                            content_bottom - inset(bottom) - block_h)
    baseline_i       = block_top + asc + i * advance
    text x (left)    = x + inset(left)

Reference constants measured from the Java engine render (LETTER, 40pt margins):
Arial 10 asc=10.06, Arial-Bold 10 asc=10.10, Arial-Bold 16 asc=16.16,
Arial 8 asc=8.05, Serif 10 asc=8.98 (= Type1 Times-Roman bbox 898).
"""
import io
import re
import zipfile
from typing import List, Tuple

WRAP = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
OVER = "overflow lima mike november oscar papa"

# (text, x, y, w, h, opts) — text starts with the probe id
PROBES = [
    ("T1 Reg10",  0,   0, 90, 20, {}),
    ("T2 Bold10", 100, 0, 90, 20, {"bold": True}),
    ("T3 Bold16", 200, 0, 110, 25, {"bold": True, "size": 16}),
    ("T4 Reg8",   320, 0, 90, 20, {"size": 8}),
    ("T5 Serif",  420, 0, 100, 20, {"serif": True}),
    ("P1 PadT3",  0,   40, 90, 25, {"pad_t": 3}),
    ("P2 BTpad",  100, 40, 90, 25, {"pad_t": 3, "bt": 0.75}),
    ("P3 BT2",    200, 40, 90, 25, {"bt": 2}),
    ("P4 PadLR",  300, 40, 100, 25, {"pad_l": 5, "pad_r": 5}),
    ("M1 Mid10",  0,   90, 90, 20, {"valign": "middle"}),
    ("M2 MidB",   100, 90, 90, 20, {"valign": "middle", "bold": True}),
    ("M3 Mid16",  200, 90, 110, 30, {"valign": "middle", "bold": True, "size": 16}),
    ("M4 MidPT4", 320, 90, 90, 20, {"valign": "middle", "pad_t": 4}),
    ("M5 MidBB",  420, 90, 100, 20, {"valign": "middle", "bt": 0.75, "bb": 0.75}),
    ("B1 Bot10",  0,   130, 90, 20, {"valign": "bottom"}),
    ("B2 BotPB1", 100, 130, 90, 20, {"valign": "bottom", "pad_b": 1}),
    ("B3 BotBPB", 200, 130, 90, 20, {"valign": "bottom", "bold": True, "pad_b": 1}),
    ("B4 BotBB",  300, 130, 90, 20, {"valign": "bottom", "bb": 0.75}),
    ("B5 Bot16",  400, 130, 100, 20, {"valign": "bottom", "bold": True, "size": 16}),
    ("W1 " + WRAP, 0,   170, 100, 60, {}),
    ("W2 " + WRAP, 120, 170, 100, 60, {"bold": True}),
    ("W3 " + WRAP, 240, 170, 100, 60, {"size": 8}),
    ("W4 " + WRAP, 360, 170, 100, 60, {"dyn": True}),
    ("O1 " + OVER, 0,   260, 100, 20, {"valign": "bottom"}),
    ("O2 " + OVER, 150, 260, 100, 20, {"valign": "middle"}),
    ("O3 " + OVER, 300, 260, 100, 20, {}),
    ("L1 Box",    0,   340, 100, 20, {"box": 0.75}),
]

MARGIN = 40.0
PAGE_H = 792.0


def _style_xml(x, y, w, h, o):
    borders = []
    for side, key in (("top", "bt"), ("bottom", "bb")):
        if o.get(key):
            borders.append('border-%s-width="%s" border-%s-color="black" border-%s-style="solid"'
                           % (side, o[key], side, side))
    if o.get("box"):
        borders.append('border-width="%s" border-style="solid"' % o["box"])
    pads = []
    for side, key in (("top", "pad_t"), ("bottom", "pad_b"), ("left", "pad_l"), ("right", "pad_r")):
        if o.get(key) is not None:
            pads.append('padding-%s="%s"' % (side, o[key]))
    parts = []
    if borders or pads:
        parts.append("<border-styles %s/>" % " ".join(pads + borders))
    common = ['alignment="left"', 'vertical-alignment="%s"' % o.get("valign", "top")]
    if o.get("dyn"):
        common.append('dynamic-height="true"')
    parts.append("<common-styles %s/>" % " ".join(common))
    parts.append('<spatial-styles x="%s" y="%s" min-width="%s" min-height="%s"/>' % (x, y, w, h))
    text = []
    if not o.get("serif"):
        text.append('font-face="Arial"')
    if o.get("size"):
        text.append('font-size="%s"' % o["size"])
    if o.get("bold"):
        text.append('bold="true"')
    if text:
        parts.append("<text-styles %s/>" % " ".join(text))
    return "<element-style>%s</element-style>" % "".join(parts)


def build_prpt() -> bytes:
    """A minimal .prpt bundle containing only the probe grid."""
    labels = "\n    ".join(
        "<layout:label>%s<core:value>%s</core:value></layout:label>" % (_style_xml(x, y, w, h, o), text)
        for text, x, y, w, h, o in PROBES)
    styles = """<?xml version="1.0" encoding="UTF-8"?>
<style xmlns="http://reporting.pentaho.org/namespaces/engine/classic/bundle/style/1.0" xmlns:layout="http://reporting.pentaho.org/namespaces/engine/classic/bundle/layout/1.0" xmlns:core="http://reporting.pentaho.org/namespaces/engine/attributes/core">
  <page-definition pageformat="LETTER" orientation="portrait" margin-top="40" margin-left="40" margin-bottom="40" margin-right="40"/>
  <layout:page-header>
    %s
  </layout:page-header>
  <layout:page-footer>
  </layout:page-footer>
</style>
""" % labels
    layout = """<?xml version="1.0" encoding="UTF-8"?>
<layout xmlns="http://reporting.pentaho.org/namespaces/engine/classic/bundle/layout/1.0" xmlns:core="http://reporting.pentaho.org/namespaces/engine/attributes/core">
  <report-header><root-level-content/></report-header>
  <group core:group-fields="">
    <fields/>
    <group-header><root-level-content/></group-header>
    <data-body>
      <details><root-level-content/></details>
      <no-data><root-level-content/></no-data>
    </data-body>
    <group-footer><root-level-content/></group-footer>
  </group>
  <report-footer><root-level-content/></report-footer>
</layout>
"""
    datadef = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<data-definition xmlns="http://reporting.pentaho.org/namespaces/'
               'engine/classic/bundle/data/1.0"/>\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("styles.xml", styles)
        zf.writestr("layout.xml", layout)
        zf.writestr("datadefinition.xml", datadef)
    return buf.getvalue()


# ── tiny PDF content-stream reader (positions in top-down page coords) ──

_NUM = r"[-+]?\d*\.?\d+"


def pdf_text_items(pdf_bytes: bytes) -> List[Tuple[float, float, str]]:
    """(x, y_top, text) for every text-showing operator, all pages."""
    from pypdf import PdfReader

    items = []
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        contents = page.get_contents()
        if contents is None:
            continue
        stream = contents.get_data().decode("latin-1")
        for bt in re.finditer(r"BT(.*?)ET", stream, re.S):
            x = y = 0.0
            for m in re.finditer(
                    r"({n})\s+({n})\s+({n})\s+({n})\s+({n})\s+({n})\s+Tm|"
                    r"({n})\s+({n})\s+Td|"
                    r"\(((?:[^()\\]|\\.)*)\)\s*Tj".format(n=_NUM), bt.group(1), re.S):
                g = m.groups()
                if g[0] is not None:
                    x, y = float(g[4]), float(g[5])
                elif g[6] is not None:
                    x, y = x + float(g[6]), y + float(g[7])
                else:
                    items.append((round(x, 2), round(PAGE_H - y, 2), g[8]))
    return items


def pdf_image_placements(pdf_bytes: bytes) -> List[dict]:
    """Placement of image XObjects: x, y_top, w, h (top-down coords)."""
    from pypdf import PdfReader

    out = []
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        contents = page.get_contents()
        if contents is None:
            continue
        stream = contents.get_data().decode("latin-1")
        for m in re.finditer(
                r"({n})\s+({n})\s+({n})\s+({n})\s+({n})\s+({n})\s+cm\s+/([\w.]+)\s+Do".format(n=_NUM),
                stream):
            a, _b, _c, d, e, f = (float(v) for v in m.groups()[:6])
            out.append({"name": m.group(7), "w": round(a, 2), "h": round(d, 2),
                        "x": round(e, 2), "y_top": round(PAGE_H - (f + d), 2)})
    return out


def probe_lines(items, probe, y_slack=45.0):
    """Baselines belonging to one probe, matched by its id prefix and column."""
    text, x, y, w, _h, _o = probe
    pid = text.split()[0]
    got = [(iy, ix, s) for ix, iy, s in items
           if MARGIN + x - 2 <= ix <= MARGIN + x + w + 2
           and MARGIN + y - 20 <= iy <= MARGIN + y + 60 + y_slack
           and (s.startswith(pid) or _same_block(s, text))]
    return sorted(got)


def _same_block(s, probe_text):
    words = probe_text.split()[1:]
    first = s.split()[0] if s.split() else ""
    return bool(first) and first in words
