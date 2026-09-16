"""Font resolution: map Pentaho font faces to reportlab's base-14 fonts.

The Java engine's PDF output writes Arial/SansSerif as the standard,
non-embedded Helvetica (and Serif as Times, Monospaced as Courier), so the
native engine does the same. Embedding a host TTF instead (Liberation Sans on
Odoo.sh, Arial on macOS) changes glyph shapes and widths from host to host.
"""
from typing import Optional

# Pentaho's engine-wide default element font
DEFAULT_FACE = "Serif"
DEFAULT_SIZE = 10.0

_HELVETICA = {
    (False, False): "Helvetica",
    (True, False): "Helvetica-Bold",
    (False, True): "Helvetica-Oblique",
    (True, True): "Helvetica-BoldOblique",
}

_TIMES = {
    (False, False): "Times-Roman",
    (True, False): "Times-Bold",
    (False, True): "Times-Italic",
    (True, True): "Times-BoldItalic",
}

_COURIER = {
    (False, False): "Courier",
    (True, False): "Courier-Bold",
    (False, True): "Courier-Oblique",
    (True, True): "Courier-BoldOblique",
}


def resolve(face: Optional[str], bold: bool = False, italic: bool = False) -> str:
    face = face or DEFAULT_FACE
    key = (bool(bold), bool(italic))
    lowered = face.lower()
    if lowered in ("serif", "times", "times new roman", "times-roman"):
        return _TIMES[key]
    if lowered in ("monospaced", "courier", "courier new"):
        return _COURIER[key]
    # arial, sansserif, helvetica, dialog — and any unknown face, rather than
    # failing the whole report
    return _HELVETICA[key]
