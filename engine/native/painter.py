"""Low-level drawing on a reportlab canvas, in top-down page coordinates.

All boxes are (x, y, w, h) with y measured from the TOP of the page (like the
.prpt layout); conversion to PDF's bottom-left origin happens here only.

Text geometry follows the model calibrated against the Java engine (see
native/tests/calibration.py): line advance equals the font size, the first
baseline sits bbox-yMax below the block top, and borders inset the content
box by their full width (their stroke is drawn at half width inside the box).
"""
from __future__ import annotations

import io
import logging

from reportlab.lib import colors as rl_colors
from reportlab.pdfbase import pdfmetrics

from . import fonts
from .model import Style

_logger = logging.getLogger(__name__)


def parse_color(value: str | None) -> tuple[float, float, float] | None:
    """Parse a Pentaho color string into an (r, g, b) 0-1 tuple, or None.

    Accepts "#rrggbb", the short form "#rgb", and named colors as seen in
    real bundles ("white", "black", "light_gray", ...) — resolved via
    reportlab's named-color table, normalizing away underscores/spaces and
    trying both the "gray"/"grey" spellings since Pentaho uses "light_gray"
    but reportlab only has "lightgrey".
    """
    if not value:
        return None
    v = value.strip()
    if not v or v.lower() == "none":
        return None
    if v.startswith("#"):
        hexpart = v[1:]
        if len(hexpart) == 3:
            hexpart = "".join(c * 2 for c in hexpart)
        if len(hexpart) != 6:
            return None
        try:
            r = int(hexpart[0:2], 16) / 255.0
            g = int(hexpart[2:4], 16) / 255.0
            b = int(hexpart[4:6], 16) / 255.0
        except ValueError:
            return None
        return (r, g, b)
    key = v.lower().replace("_", "").replace(" ", "")
    named = rl_colors.getAllNamedColors()
    color = named.get(key)
    if color is None and "gray" in key:
        color = named.get(key.replace("gray", "grey"))
    if color is None and "grey" in key:
        color = named.get(key.replace("grey", "gray"))
    if color is None:
        return None
    return (color.red, color.green, color.blue)

# Adobe base-14 FontBBox yMax (per mille); TTF faces carry their own bbox.
_TYPE1_BBOX_YMAX = {
    "Times-Roman": 898.0, "Times-Bold": 935.0,
    "Times-Italic": 883.0, "Times-BoldItalic": 921.0,
    "Helvetica": 931.0, "Helvetica-Bold": 962.0,
    "Helvetica-Oblique": 931.0, "Helvetica-BoldOblique": 962.0,
    "Courier": 805.0, "Courier-Bold": 801.0,
    "Courier-Oblique": 805.0, "Courier-BoldOblique": 801.0,
}


def max_ascent(font: str, size: float) -> float:
    """First-baseline offset from the block top: bbox yMax (Java engine model)."""
    ymax = _TYPE1_BBOX_YMAX.get(font)
    if ymax is None:
        face = pdfmetrics.getFont(font).face
        bbox = getattr(face, "bbox", None)
        ymax = bbox[3] if bbox else pdfmetrics.getAscent(font)
    return ymax / 1000.0 * size


def line_height(size: float) -> float:
    # the Java engine advances lines by exactly the font size (no leading)
    return size


def wrap_text(text: str, font: str, size: float, width: float) -> list[str]:
    """Word-wrap text to the given width; hard-break oversized words."""
    width = max(1.0, width)
    lines: list[str] = []
    for raw_line in (text or "").splitlines() or [""]:
        words = raw_line.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if pdfmetrics.stringWidth(candidate, font, size) <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        # hard-break a single word wider than the box
        while pdfmetrics.stringWidth(current, font, size) > width and len(current) > 1:
            cut = len(current)
            while cut > 1 and pdfmetrics.stringWidth(current[:cut], font, size) > width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
        lines.append(current)
    return lines


def text_block_height(num_lines: int, size: float) -> float:
    return num_lines * size


def _insets(style: Style) -> dict[str, float]:
    """Content-box inset per side = padding + border width (Java box model)."""
    out = {}
    for side in ("top", "bottom", "left", "right"):
        border = style.borders.get(side)
        out[side] = style.padding.get(side, 0.0) + (border.width if border else 0.0)
    return out


class Painter:
    def __init__(self, canvas, page_height: float):
        self.c = canvas
        self.page_h = page_height

    # ── coordinate helpers ──────────────────────────────────

    def _pdf_y(self, top_y: float) -> float:
        return self.page_h - top_y

    # ── text ────────────────────────────────────────────────

    def measure_text(self, text: str, style: Style, width: float) -> float:
        font, size = self._font(style)
        ins = _insets(style)
        lines = wrap_text(text, font, size, width - ins["left"] - ins["right"])
        return text_block_height(len(lines), size) + ins["top"] + ins["bottom"]

    def draw_text(self, box, text: str, style: Style) -> None:
        if text is None or text == "":
            return
        x, y, w, h = box
        font, size = self._font(style)
        ins = _insets(style)
        inner_w = max(1.0, w - ins["left"] - ins["right"])
        lines = wrap_text(text, font, size, inner_w)

        # min-height is a minimum: all wrapped lines render even when the
        # element is not dynamic-height (matches the Java engine)
        block_h = text_block_height(len(lines), size)
        content_top = y + ins["top"]
        content_bottom = y + h - ins["bottom"]

        valign = style.valign or "top"
        if valign == "middle":
            top = max(content_top, (content_top + content_bottom) / 2.0 - block_h / 2.0)
        elif valign == "bottom":
            # the engine aligns the block bottom a further bottom-inset up,
            # clamped so the block never starts above the content top
            top = max(content_top, content_bottom - ins["bottom"] - block_h)
        else:
            top = content_top

        asc = max_ascent(font, size)
        self.c.setFont(font, size)
        self.c.setFillColorRGB(0, 0, 0)
        align = style.align or "left"
        for i, line in enumerate(lines):
            pdf_y = self._pdf_y(top + asc + i * size)
            if align == "right":
                self.c.drawRightString(x + w - ins["right"], pdf_y, line)
                line_x = x + w - ins["right"] - pdfmetrics.stringWidth(line, font, size)
            elif align == "center":
                self.c.drawCentredString(x + ins["left"] + inner_w / 2.0, pdf_y, line)
                line_x = x + ins["left"] + (inner_w - pdfmetrics.stringWidth(line, font, size)) / 2.0
            else:
                self.c.drawString(x + ins["left"], pdf_y, line)
                line_x = x + ins["left"]
            if style.underline:
                lw = pdfmetrics.stringWidth(line, font, size)
                self.c.setLineWidth(max(0.5, size / 18.0))
                self.c.line(line_x, pdf_y - 1.5, line_x + lw, pdf_y - 1.5)

    def _font(self, style: Style) -> tuple[str, float]:
        size = style.font_size or fonts.DEFAULT_SIZE
        return fonts.resolve(style.font_face, style.bold, style.italic), size

    # ── borders / lines / images ────────────────────────────

    def fill_background(self, box, style: Style) -> None:
        """Fill the box with style.bg_color, if any — drawn BEHIND borders,
        text, and shape strokes. General for any element kind (not just
        rectangle): a report can put a background-color on a label/band too.
        """
        rgb = parse_color(style.bg_color)
        if rgb is None:
            return
        x, y, w, h = box
        if w <= 0 or h <= 0:
            return
        self.c.setFillColorRGB(*rgb)
        self.c.rect(x, self._pdf_y(y + h), w, h, stroke=0, fill=1)

    def draw_borders(self, box, style: Style) -> None:
        if not style.borders:
            return
        x, y, w, h = box
        self.c.setStrokeColorRGB(0, 0, 0)
        for side, border in style.borders.items():
            self.c.setLineWidth(border.width)
            inset = border.width / 2.0  # stroke centered just inside the edge
            top, bottom = self._pdf_y(y + inset), self._pdf_y(y + h - inset)
            if side == "top":
                self.c.line(x, top, x + w, top)
            elif side == "bottom":
                self.c.line(x, bottom, x + w, bottom)
            elif side == "left":
                self.c.line(x + inset, self._pdf_y(y + h), x + inset, self._pdf_y(y))
            elif side == "right":
                self.c.line(x + w - inset, self._pdf_y(y + h), x + w - inset, self._pdf_y(y))

    def draw_hline(self, box, style: Style) -> None:
        x, y, w, _h = box
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.setLineWidth(1.0)
        self.c.line(x, self._pdf_y(y), x + w, self._pdf_y(y))

    def draw_vline(self, box, style: Style) -> None:
        x, y, _w, h = box
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.setLineWidth(1.0)
        self.c.line(x, self._pdf_y(y), x, self._pdf_y(y + h))

    def draw_rect(self, box, style: Style) -> None:
        if style.draw_shape is False:
            return
        if style.borders:
            self.draw_borders(box, style)
            return
        x, y, w, h = box
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.setLineWidth(1.0)
        self.c.rect(x, self._pdf_y(y + h), w, h, stroke=1, fill=0)

    def draw_image(self, box, data, style: Style) -> None:
        if not data:
            return
        if isinstance(data, memoryview):
            data = bytes(data)
        if not isinstance(data, (bytes, bytearray)):
            return
        try:
            from reportlab.lib.utils import ImageReader

            x, y, w, h = box
            # anchor from the element's alignment (Pentaho honors it; default
            # top-left), e.g. the report logos are alignment=left valign=middle
            horiz = {"left": "w", "center": "", "right": "e"}.get(style.align or "left", "w")
            vert = {"top": "n", "middle": "", "bottom": "s"}.get(style.valign or "top", "n")
            anchor = (vert + horiz) or "c"
            self.c.drawImage(
                ImageReader(io.BytesIO(bytes(data))),
                x, self._pdf_y(y + h), w, h,
                preserveAspectRatio=style.keep_aspect,
                anchor=anchor,
                mask="auto",
            )
        except Exception:
            _logger.warning("native renderer: could not draw image", exc_info=True)

    # Pentaho simple-barcodes @type → reportlab createBarcodeDrawing name.
    _BARCODE_SYMBOLOGIES = {
        "code128": "Code128",
        "code39": "Standard39",
        "ean13": "EAN13",
    }

    def draw_barcode(self, box, value, barcode_type, style: Style) -> None:
        if value is None or value == "":
            return
        x, y, w, h = box
        if w <= 0 or h <= 0:
            return
        name = self._BARCODE_SYMBOLOGIES.get((barcode_type or "").lower(), "Code128")
        try:
            from reportlab.graphics.barcode import createBarcodeDrawing

            drawing = createBarcodeDrawing(name, value=str(value), width=w, height=h)
            drawing.drawOn(self.c, x, self._pdf_y(y + h))
        except Exception:
            # an unencodable value for the symbology (e.g. non-numeric for
            # EAN13) or any other barcode-generation failure must not crash
            # the whole report — skip this element, matching draw_image.
            _logger.warning(
                "native renderer: could not draw barcode (type=%r, value=%r)",
                barcode_type, value, exc_info=True,
            )
