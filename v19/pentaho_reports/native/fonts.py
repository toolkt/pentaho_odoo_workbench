"""Font resolution: map Pentaho font faces to registered reportlab fonts.

Tries real TTFs (macOS Arial, Linux Liberation Sans) so output matches the
Java engine's metrics; falls back to the metrically-similar base-14 fonts.
"""
import logging
import os
from typing import Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_logger = logging.getLogger(__name__)

# Pentaho's engine-wide default element font
DEFAULT_FACE = "Serif"
DEFAULT_SIZE = 10.0

_VARIANTS = [(False, False), (True, False), (False, True), (True, True)]

_ARIAL_FILES = {
    (False, False): ["/System/Library/Fonts/Supplemental/Arial.ttf",
                     "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    (True, False): ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    (False, True): ["/System/Library/Fonts/Supplemental/Arial Italic.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf"],
    (True, True): ["/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf"],
}

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

_arial_family = None  # type: Optional[dict]


def _register_arial() -> dict:
    global _arial_family
    if _arial_family is not None:
        return _arial_family
    family = {}
    for variant in _VARIANTS:
        for path in _ARIAL_FILES[variant]:
            if os.path.exists(path):
                name = "PrptArial" + ("-Bold" if variant[0] else "") + ("-Italic" if variant[1] else "")
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    family[variant] = name
                    break
                except Exception:
                    _logger.debug("could not register font %s", path, exc_info=True)
    # fill gaps with Helvetica equivalents
    for variant in _VARIANTS:
        family.setdefault(variant, _HELVETICA[variant])
    _arial_family = family
    return family


def resolve(face: Optional[str], bold: bool = False, italic: bool = False) -> str:
    face = face or DEFAULT_FACE
    key = (bold, italic)
    lowered = face.lower()
    if lowered in ("arial", "sansserif", "sans-serif", "helvetica", "dialog"):
        return _register_arial()[key]
    if lowered in ("serif", "times", "times new roman"):
        return _TIMES[key]
    if lowered in ("monospaced", "courier", "courier new"):
        return _COURIER[key]
    # unknown face: use Arial-alike rather than failing the whole report
    return _register_arial()[key]
