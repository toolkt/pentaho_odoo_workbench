"""Vendored fixtures must not carry database credentials (sql-ds.xml connection block)."""
import re
import zipfile

import pytest

from conftest import FIXTURES_DIR

EXPECTED = {
    "delivery_receipt.prpt", "sales_invoice.prpt", "ap_voucher.prpt", "BIR_2307.prpt",
    "evergood_sale_report.prpt", "gl_listing_nested.prpt", "print_supplier_check.prpt",
    "product_barcode.prpt",
}


def _sql_ds_parts(path):
    with zipfile.ZipFile(str(path)) as zf:
        for name in zf.namelist():
            if name.endswith("sql-ds.xml"):
                yield name, zf.read(name).decode("utf-8", "replace")


def test_all_expected_fixtures_present():
    if FIXTURES_DIR is None:
        pytest.skip("fixtures dir not found")
    present = {p.name for p in FIXTURES_DIR.glob("*.prpt")}
    assert EXPECTED <= present, sorted(EXPECTED - present)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_has_no_credentials(name):
    if FIXTURES_DIR is None:
        pytest.skip("fixtures dir not found")
    parts = list(_sql_ds_parts(FIXTURES_DIR / name))
    assert parts, "fixture has no sql-ds.xml?"
    for part, xml in parts:
        assert "encrypted:" not in xml, part
        users = re.findall(r'<data:property name="user">([^<]*)</data:property>', xml)
        assert users and set(users) == {"demo"}, (part, users)
        passwords = re.findall(r'<data:property name="password">([^<]*)</data:property>', xml)
        assert set(passwords) <= {""}, (part, passwords)
        urls = re.findall(r"<data:url>([^<]*)</data:url>", xml)
        assert set(urls) <= {"jdbc:postgresql://localhost/demo"}, (part, urls)
        assert "::pentaho-reporting::hostname\">" not in xml or \
            re.search(r'name="::pentaho-reporting::hostname">localhost<', xml), part


def test_mimetype_is_first_and_stored():
    if FIXTURES_DIR is None:
        pytest.skip("fixtures dir not found")
    for name in sorted(EXPECTED):
        with zipfile.ZipFile(str(FIXTURES_DIR / name)) as zf:
            first = zf.infolist()[0]
            assert first.filename == "mimetype", name
            assert first.compress_type == zipfile.ZIP_STORED, name
