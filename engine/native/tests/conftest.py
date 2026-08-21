"""Shared test wiring for the native engine.

* Puts the directory containing the `native` package on sys.path so tests
  import `native.*` whether they run from engine/native/tests (canonical)
  or from vNN/pentaho_reports/native/tests (synced copy).
* Locates the vendored .prpt fixtures: $PENTAHO_FIXTURES, else the nearest
  ancestor `fixtures/` dir containing delivery_receipt.prpt. When absent,
  fixture-backed tests SKIP (never FileNotFoundError).
"""
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PACKAGE_PARENT = HERE.parents[1]  # dir that contains the `native` package
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

MODULE_DIR = PACKAGE_PARENT  # kept for older imports


def _find_fixtures_dir():
    env = os.environ.get("PENTAHO_FIXTURES")
    if env:
        return Path(env)
    for parent in HERE.parents:
        candidate = parent / "fixtures"
        if (candidate / "delivery_receipt.prpt").exists():
            return candidate
    return None


FIXTURES_DIR = _find_fixtures_dir()


class _FixturePath(type(Path())):
    """A Path whose read_bytes() skips the current test when the file is absent."""

    def read_bytes(self):
        if not self.exists():
            pytest.skip("vendored .prpt fixture not available: %s "
                        "(set PENTAHO_FIXTURES or run inside the repo)" % self)
        return super().read_bytes()


def fixture_path(name):
    base = FIXTURES_DIR if FIXTURES_DIR is not None else Path("/nonexistent/pentaho-fixtures")
    return _FixturePath(base / name)


DELIVERY_RECEIPT_PRPT = fixture_path("delivery_receipt.prpt")
SALES_INVOICE_PRPT = fixture_path("sales_invoice.prpt")
AP_VOUCHER_PRPT = fixture_path("ap_voucher.prpt")
BIR_2307_PRPT = fixture_path("BIR_2307.prpt")
EVERGOOD_SALE_REPORT_PRPT = fixture_path("evergood_sale_report.prpt")
# real-world multi-level (nested group-body) sample: a GL listing grouped by
# account then sub-account
GL_LISTING_NESTED_PRPT = fixture_path("gl_listing_nested.prpt")
# has a <date-field format-string="MM/dd/yyyy"> and nothing else unsupported
PRINT_SUPPLIER_CHECK_PRPT = fixture_path("print_supplier_check.prpt")
# real-world code128 <sbarcodes:simple-barcodes> sample (product label sheet)
BARCODE_PRPT = fixture_path("product_barcode.prpt")
# synthetic: evergood_sale_report with its query re-pointed at res_partner
PARTNER_LIST_PRPT = fixture_path("partner_list.prpt")
