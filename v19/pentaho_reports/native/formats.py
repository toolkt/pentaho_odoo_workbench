"""Java DecimalFormat subset + default value formatting.

number-fields without an explicit format-string are rendered the way Java's
NumberFormat.getInstance() does it (grouping, 0-3 fraction digits, half-even),
which is what the Pentaho engine falls back to.
"""
import datetime
import re
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Optional

_PATTERN = re.compile(r"^([^#0]*)([#,0]+)(?:\.([#0]+))?([^#0]*)$")


def _group(int_value: int) -> str:
    return format(int_value, ",")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _java_default(value) -> str:
    d = _to_decimal(value)
    q = d.quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
    text = format(q, "f")
    int_part, _, frac = text.partition(".")
    frac = frac.rstrip("0")
    negative = int_part.startswith("-")
    out = _group(abs(int(int_part)))
    if frac:
        out += "." + frac
    return ("-" if negative else "") + out


def _apply_subpattern(value: Decimal, prefix: str, int_pat: str, frac_pat: str, suffix: str) -> str:
    max_frac = len(frac_pat)
    min_frac = frac_pat.count("0")
    grouping = "," in int_pat

    exponent = Decimal(1).scaleb(-max_frac) if max_frac else Decimal(1)
    q = value.quantize(exponent, rounding=ROUND_HALF_EVEN)
    text = format(q, "f")
    int_part, _, frac = text.partition(".")
    frac = frac.rstrip("0")
    while len(frac) < min_frac:
        frac += "0"

    int_text = _group(int(int_part)) if grouping else int_part
    min_int = int_pat.replace(",", "").count("0")
    digits_only = int_text.replace(",", "")
    while len(digits_only) < min_int:
        int_text = "0" + int_text
        digits_only = "0" + digits_only

    out = int_text
    if frac:
        out += "." + frac
    return prefix + out + suffix


def format_number(value, pattern: Optional[str]) -> str:
    if pattern is None:
        return _java_default(value)

    positive, _, negative = pattern.partition(";")
    d = _to_decimal(value)

    if d < 0 and negative:
        m = _PATTERN.match(negative)
        if m:
            return _apply_subpattern(-d, m.group(1), m.group(2), m.group(3) or "", m.group(4))
    m = _PATTERN.match(positive)
    if not m:
        return _java_default(value)
    sign = "-" if d < 0 else ""
    return sign + _apply_subpattern(abs(d), m.group(1), m.group(2), m.group(3) or "", m.group(4))


# Java SimpleDateFormat symbol runs → strftime directives. Longer runs are
# looked up before shorter ones would be considered (dict lookup is by exact
# (symbol, run-length) pair, so e.g. "MMMM" can never be mistaken for "MM").
_DATE_TOKEN_MAP = {
    ("y", 4): "%Y",
    ("y", 2): "%y",
    ("M", 4): "%B",
    ("M", 3): "%b",
    ("M", 2): "%m",
    ("d", 2): "%d",
    ("d", 1): "%d",  # Java's bare "d" has no leading zero; %d always pads —
                      # acceptable approximation, documented in the report.
    ("E", 4): "%A",
    ("E", 3): "%a",
    ("H", 2): "%H",
    ("h", 2): "%I",
    ("m", 2): "%M",
    ("s", 2): "%S",
    ("a", 1): "%p",
}

# separator/punctuation characters passed through the format literally
_DATE_LITERAL_CHARS = set("/-: ,.")


def java_dateformat_to_strftime(pattern: str) -> Optional[str]:
    """Translate a (subset of) Java SimpleDateFormat pattern to a Python
    strftime format string.

    Returns None when the pattern contains a letter run or punctuation
    character we don't recognize — callers must treat that as "unsupported"
    and fall back to a safe default rather than risk emitting a wrong or
    partial format.
    """
    out = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch.isalpha():
            j = i
            while j < n and pattern[j] == ch:
                j += 1
            token = _DATE_TOKEN_MAP.get((ch, j - i))
            if token is None:
                return None
            out.append(token)
            i = j
        elif ch in _DATE_LITERAL_CHARS:
            out.append(ch)
            i += 1
        else:
            return None
    return "".join(out)


def format_value(value, pattern: Optional[str]) -> str:
    if value is None or value is False:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, Decimal)):
        return format_number(value, pattern)
    if isinstance(value, (datetime.datetime, datetime.date)):
        if pattern:
            strftime_fmt = java_dateformat_to_strftime(pattern)
            if strftime_fmt is not None:
                return value.strftime(strftime_fmt)
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value.strftime("%Y-%m-%d")
    return str(value)
