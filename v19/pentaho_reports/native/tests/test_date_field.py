"""date-field support: a real corpus .prpt that uses <date-field> must render
instead of raising UnsupportedFeature (previously ~57% of Piaggio-style
reports used date-field and could not render at all).
"""
import datetime

import pytest

from conftest import PRINT_SUPPLIER_CHECK_PRPT

import native.bundle as bundle_mod
from native.bundle import PrptBundle
from native.model import UnsupportedFeature
from native.renderer import NativeRenderer

# picked because it has a <date-field field="check_date"
# format-string="MM/dd/yyyy"> and nothing else this renderer doesn't support
# (no <rectangle>, no <sub-report>, no <style-expression>) — proves
# date-field alone, not some other unsupported element, is what's under test.
CHECK_VOUCHER_PRPT = PRINT_SUPPLIER_CHECK_PRPT


def _row(**over):
    row = {
        "supplier": "Some Vendor Inc",
        "check_date": datetime.date(2026, 8, 12),
        "amount": 1000.0,
        "amount_words": "One Thousand Pesos Only",
    }
    row.update(over)
    return row


def make_renderer(rows):
    def execute_query(sql, params):
        return rows

    return NativeRenderer(execute_query)


def test_date_field_kind_is_no_longer_unsupported():
    # RED-verify: confirm this exact bundle raised UnsupportedFeature before
    # the fix, by temporarily simulating the pre-fix ELEMENT_KINDS set.
    original = bundle_mod.ELEMENT_KINDS
    bundle_mod.ELEMENT_KINDS = original - {"date-field"}
    try:
        with pytest.raises(UnsupportedFeature, match="date-field"):
            PrptBundle.from_bytes(CHECK_VOUCHER_PRPT.read_bytes())
    finally:
        bundle_mod.ELEMENT_KINDS = original

    # GREEN: with date-field restored, parsing no longer raises.
    PrptBundle.from_bytes(CHECK_VOUCHER_PRPT.read_bytes())


def test_date_field_report_renders_to_pdf():
    out = make_renderer([_row()]).render(CHECK_VOUCHER_PRPT.read_bytes(), {"ids": [1]})
    assert out.startswith(b"%PDF")
    assert len(out) > 0


def test_date_field_honors_format_string_in_output():
    """check_date's format-string is MM/dd/yyyy → '08/12/2026', not ISO."""
    from pypdf import PdfReader
    import io

    out = make_renderer([_row(check_date=datetime.date(2026, 8, 12))]).render(
        CHECK_VOUCHER_PRPT.read_bytes(), {"ids": [1]}
    )
    reader = PdfReader(io.BytesIO(out))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "08/12/2026" in text
    assert "2026-08-12" not in text
