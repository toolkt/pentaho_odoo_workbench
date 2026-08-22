"""Java DecimalFormat subset used by the Piaggio reports."""
import datetime
from decimal import Decimal

from native.formats import format_number, format_value


def test_explicit_pattern_positive():
    assert format_number(1234.5, "#,##0.00;(#,##0.00)") == "1,234.50"


def test_explicit_pattern_negative_uses_suffix_form():
    assert format_number(-1234.5, "#,##0.00;(#,##0.00)") == "(1,234.50)"


def test_default_matches_java_getnumberinstance():
    # Java NumberFormat.getInstance(): grouping on, 0..3 fraction digits
    assert format_number(1500.0, None) == "1,500"
    assert format_number(1234.5, None) == "1,234.5"
    assert format_number(1234.5678, None) == "1,234.568"
    assert format_number(Decimal("0.125"), None) == "0.125"
    assert format_number(7, None) == "7"


def test_format_value_passthrough_and_none():
    assert format_value(None, None) == ""
    assert format_value("already a string", None) == "already a string"
    assert format_value(Decimal("2.50"), None) == "2.5"


def test_format_value_date_honors_java_pattern():
    assert format_value(datetime.date(2026, 8, 12), "MM/dd/yyyy") == "08/12/2026"


def test_format_value_datetime_honors_java_pattern():
    assert format_value(
        datetime.datetime(2026, 8, 12, 14, 30), "yyyy-MM-dd HH:mm"
    ) == "2026-08-12 14:30"


def test_format_value_date_month_name_pattern():
    # "d" (bare, not "dd") is mapped to %d in this implementation, which
    # zero-pads single-digit days (Java's bare "d" would not) — see caveat
    # in the follow-up report.
    assert format_value(datetime.date(2026, 8, 12), "MMMM d, yyyy") == "August 12, 2026"


def test_format_value_date_unrecognized_pattern_falls_back_to_iso():
    assert format_value(datetime.date(2026, 8, 12), "Q'foo'") == "2026-08-12"


def test_format_value_date_empty_or_none_pattern_is_iso():
    assert format_value(datetime.date(2026, 8, 12), None) == "2026-08-12"
    assert format_value(datetime.date(2026, 8, 12), "") == "2026-08-12"
    assert format_value(
        datetime.datetime(2026, 8, 12, 14, 30, 5), None
    ) == "2026-08-12 14:30:05"
