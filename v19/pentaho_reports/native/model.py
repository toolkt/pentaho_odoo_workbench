"""Parsed representation of a .prpt bundle (subset)."""
import logging
from typing import Dict, List, Optional, Tuple

_logger = logging.getLogger(__name__)


class UnsupportedFeature(Exception):
    """The .prpt uses something the native renderer does not implement."""


class _Record(object):
    """Minimal stand-in for @dataclass (the engine must import on Python 3.6):
    keyword constructor with per-instance defaults, field-wise equality, repr.

    Subclasses list their fields in `_fields` as (name, default_or_factory,
    is_factory) tuples; `_required` names fields without a default.
    """
    _fields = ()  # type: Tuple[Tuple[str, object, bool], ...]
    _required = ()  # type: Tuple[str, ...]

    def __init__(self, *args, **kwargs):
        names = [f[0] for f in self._fields]
        if len(args) > len(names):
            raise TypeError("%s() takes at most %d positional arguments" % (type(self).__name__, len(names)))
        for name, value in zip(names, args):
            if name in kwargs:
                raise TypeError("%s() got multiple values for argument %r" % (type(self).__name__, name))
            kwargs[name] = value
        unknown = set(kwargs) - set(names)
        if unknown:
            raise TypeError("%s() got unexpected keyword argument(s): %s" % (type(self).__name__, ", ".join(sorted(unknown))))
        for name, default, is_factory in self._fields:
            if name in kwargs:
                value = kwargs[name]
            elif name in self._required:
                raise TypeError("%s() missing required argument: %r" % (type(self).__name__, name))
            else:
                value = default() if is_factory else default
            setattr(self, name, value)

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return all(getattr(self, f[0]) == getattr(other, f[0]) for f in self._fields)

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    __hash__ = None  # mutable, like an eq=True dataclass

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__,
                           ", ".join("%s=%r" % (f[0], getattr(self, f[0])) for f in self._fields))


class BorderSide(_Record):
    _fields = (("width", None, False), ("style", None, False))
    _required = ("width", "style")   # style: 'solid', 'dashed', ... (only drawable sides are stored)


class Style(_Record):
    _fields = (
        ("x", 0.0, False), ("y", 0.0, False), ("width", 0.0, False), ("height", 0.0, False),
        ("height_pct", None, False),      # min-height="100%" → 100.0
        ("font_face", None, False), ("font_size", None, False),
        ("bold", False, False), ("italic", False, False), ("underline", False, False),
        ("align", None, False),           # left | center | right
        ("valign", None, False),          # top | middle | bottom
        ("borders", dict, True),          # Dict[str, BorderSide]
        ("padding", dict, True),          # Dict[str, float]
        ("dynamic_height", False, False), ("scale", False, False), ("keep_aspect", False, False),
        ("draw_shape", False, False),
        ("bg_color", None, False),        # raw color string, e.g. "#c9c98b" or "light_gray"
    )


class Element(_Record):
    _fields = (
        ("kind", None, False),            # label | text-field | number-field | content |
        #                                   content-field | band | horizontal-line | sub-report
        ("style", Style, True),
        ("field", None, False),           # data binding
        ("value", None, False),           # label text
        ("fmt", None, False),             # explicit format-string, if any
        ("barcode_type", None, False),    # kind == simple-barcodes/simple-barcode, e.g. "code128"
        ("elements", list, True),         # kind == band  (List[Element])
        ("subreport", None, False),       # kind == sub-report
        ("resource", None, False),        # kind == content (bytes)
    )
    _required = ("kind",)


class Band(_Record):
    _fields = (("elements", list, True), ("style", Style, True))


class Group(_Record):
    _fields = (
        ("fields", list, True),
        ("header", Band, True), ("footer", Band, True), ("details", Band, True), ("no_data", Band, True),
        # a group parsed from a <group-body> sets `child` (the nested <group>) and
        # leaves details/no_data empty; a group parsed from a <data-body> is a LEAF
        # (has details/no_data, child is None). Single-level reports never set
        # this, so they keep working unchanged.
        ("child", None, False),
    )


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


class PageDef(_Record):
    _fields = (
        ("format", "LETTER", False),
        ("orientation", "portrait", False),
        ("margins", (0.0, 0.0, 0.0, 0.0), False),   # top,left,bottom,right
        ("width", 0.0, False),    # explicit page size (custom formats, e.g. BIR 612x920);
        ("height", 0.0, False),   # takes precedence over the named format
    )

    @property
    def size_pt(self):
        # type: () -> Tuple[float, float]
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


class PlainParameter(_Record):
    _fields = (
        ("name", None, False),
        ("mandatory", False, False),
        ("ptype", "java.lang.Object", False),
        ("attrs", dict, True),            # Dict[str, str]
    )
    _required = ("name",)
