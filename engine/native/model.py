"""Parsed representation of a .prpt bundle (subset)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field

_logger = logging.getLogger(__name__)


class UnsupportedFeature(Exception):
    """The .prpt uses something the native renderer does not implement."""


@dataclass
class BorderSide:
    width: float
    style: str  # 'solid', 'dashed', ... (only drawable sides are stored)


@dataclass
class Style:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    height_pct: float | None = None  # min-height="100%" → 100.0
    font_face: str | None = None
    font_size: float | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: str | None = None       # left | center | right
    valign: str | None = None      # top | middle | bottom
    borders: dict[str, BorderSide] = dc_field(default_factory=dict)
    padding: dict[str, float] = dc_field(default_factory=dict)
    dynamic_height: bool = False
    scale: bool = False
    keep_aspect: bool = False
    draw_shape: bool = False
    bg_color: str | None = None    # raw color string, e.g. "#c9c98b" or "light_gray"


@dataclass
class Element:
    kind: str                       # label | text-field | number-field | content |
    #                                 content-field | band | horizontal-line | sub-report
    style: Style = dc_field(default_factory=Style)
    field: str | None = None        # data binding
    value: str | None = None        # label text
    fmt: str | None = None          # explicit format-string, if any
    barcode_type: str | None = None  # kind == simple-barcodes/simple-barcode, e.g. "code128"
    elements: list["Element"] = dc_field(default_factory=list)   # kind == band
    subreport: "object | None" = None                         # kind == sub-report
    resource: bytes | None = None                             # kind == content


@dataclass
class Band:
    elements: list[Element] = dc_field(default_factory=list)
    style: Style = dc_field(default_factory=Style)


@dataclass
class Group:
    fields: list[str] = dc_field(default_factory=list)
    header: Band = dc_field(default_factory=Band)
    footer: Band = dc_field(default_factory=Band)
    details: Band = dc_field(default_factory=Band)
    no_data: Band = dc_field(default_factory=Band)
    # a group parsed from a <group-body> sets `child` (the nested <group>) and
    # leaves details/no_data empty; a group parsed from a <data-body> is a LEAF
    # (has details/no_data, child is None). Single-level reports never set
    # this, so they keep working unchanged.
    child: "Group | None" = None


# points per named page format (width, height) in portrait.
#
# Values for LETTER/LEGAL/A4/FOLIO/TABLOID/LEDGER/STATEMENT/PAPER9X12/
# PAPER8X10/FANFOLDGERMAN(LEGAL)/LETTER_ROTATED/LETTER_EXTRA/LEGAL_EXTRA/
# A4_ROTATED are the EXACT rectangles decompiled from the Java engine's own
# org.pentaho.reporting.engine.classic.core.util.PageSize class (in
# pentaho-reporting-engine-classic-core-5.0-SNAPSHOT.jar) — its <clinit>
# static initializer passes (width, height) in points directly to each
# constant's constructor. Notably FOLIO there is (595, 935), NOT the
# itext/other-vendor (612, 936) some references use.
#
# LEGAL_ROTATED and FANFOLDUSLEGAL are NOT defined as named constants in
# that class (a report would express "rotated legal" via orientation=
# "landscape" instead) and never appear in the sample_prpt/ corpus scan;
# kept here only as a defensive fallback with a reasonable computed value
# (a landscape swap of LEGAL / same as FANFOLDUSLEGAL's US-legal size).
PAGE_FORMATS = {
    "LETTER": (612.0, 792.0),
    "LEGAL": (612.0, 1008.0),
    "A4": (595.0, 842.0),
    "FOLIO": (595.0, 935.0),
    "LEDGER": (1224.0, 792.0),
    "TABLOID": (792.0, 1224.0),
    "LETTER_ROTATED": (792.0, 612.0),
    "LEGAL_ROTATED": (1008.0, 612.0),           # defensive fallback (see above)
    "A4_ROTATED": (842.0, 595.0),
    "LETTER_EXTRA": (684.0, 864.0),
    "LEGAL_EXTRA": (684.0, 1080.0),
    "FANFOLDGERMANLEGAL": (612.0, 936.0),
    "FANFOLDUSLEGAL": (612.0, 1008.0),          # defensive fallback (see above)
    # additional formats observed in the sample_prpt/ corpus scan, also
    # decompiled from the Java PageSize class:
    "STATEMENT": (396.0, 612.0),
    "PAPER9X12": (648.0, 864.0),
    "PAPER8X10": (576.0, 720.0),
}


@dataclass
class PageDef:
    format: str = "LETTER"
    orientation: str = "portrait"
    margins: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # top,left,bottom,right
    width: float = 0.0    # explicit page size (custom formats, e.g. BIR 612x920);
    height: float = 0.0   # takes precedence over the named format

    @property
    def size_pt(self) -> tuple[float, float]:
        if self.width and self.height:
            w, h = self.width, self.height
        else:
            wh = PAGE_FORMATS.get(self.format)
            if wh is None:
                # unknown/unseen named format — never crash the render over a
                # page size; fall back to LETTER (the corpus default) and
                # note it so gaps in PAGE_FORMATS are discoverable in logs.
                _logger.warning(
                    "unknown page format %r; falling back to LETTER", self.format
                )
                wh = PAGE_FORMATS["LETTER"]
            w, h = wh
        if self.orientation == "landscape":
            w, h = h, w
        return (w, h)


@dataclass
class PlainParameter:
    name: str
    mandatory: bool = False
    ptype: str = "java.lang.Object"
    attrs: dict[str, str] = dc_field(default_factory=dict)
