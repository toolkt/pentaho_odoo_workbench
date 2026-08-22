"""Render both real .prpt layouts with fake query results → valid PDFs."""
import io

import pytest
from pypdf import PdfReader

from conftest import DELIVERY_RECEIPT_PRPT, SALES_INVOICE_PRPT

from native.renderer import NativeRenderer


def dr_row(**over):
    row = {
        "company_logo": None,
        "company_name": "Piaggio Philippines",
        "contact_number": "123",
        "company_tin": "691-334-462-00000",
        "company_address": "9th Floor Arthaland Tower",
        "id": 50,
        "dr_number": "PHSA/IN/00001",
        "dr_date": "08/06/2026",
        "order_number": "SO0042",
        "csr_number": " ",
        "vendor_name": "Juan Dela Cruz",
        "mobile_number": "0917-555-1234",
        "vendor_address": "Makati City 1200",
        "quantity": 1.0,
        "uom": "Units",
        "product_name": "VESPA GTS 300 SUPER TECH",
        "serial_number": "MD7100001",
        "price": "310,000.00",
        "amount": "310,000.00",
    }
    row.update(over)
    return row


def si_row(move_id, **over):
    row = {
        "move_id": move_id,
        "invoice_number": "INV/2026/%05d" % move_id,
        "invoice_date": "08/06/2026",
        "registered_name": "ACME Corp",
        "customer_tin": "123-456-789-000",
        "customer_address": "BGC, Taguig",
        "payment_term": "30 Days",
        "description": "VESPA PRIMAVERA 150",
        "serial_numbers": "MD7100055",
        "uom": "Units",
        "quantity": 1,
        "price_unit": 49107.14,
        "amount": 49107.14,
        "vatable_sales": 49107.14,
        "vat_amount": 5892.86,
        "total_sales_vat_incl": 55000.0,
        "amount_net_of_vat": 49107.14,
        "zero_rated_sales": 0.0,
        "vat_exempt_sales": 0.0,
        "withholding_tax": 0.0,
        "total_before_vat_add": 49107.14,
        "total_amount_due": 55000.0,
    }
    row.update(over)
    return row


def make_renderer(rows):
    def execute_query(sql, params):
        return rows

    return NativeRenderer(execute_query)


def read_pdf(data: bytes) -> PdfReader:
    assert data.startswith(b"%PDF")
    return PdfReader(io.BytesIO(data))


def all_text(reader: PdfReader) -> str:
    return "\n".join(page.extract_text() for page in reader.pages)


# ── delivery receipt ────────────────────────────────────────

def test_dr_single_page(tmp_path):
    rows = [dr_row(), dr_row(product_name="HELMET PIAGGIO XL", serial_number=" ",
                            quantity=2.0, price="2,500.00", amount="5,000.00")]
    out = make_renderer(rows).render(DELIVERY_RECEIPT_PRPT.read_bytes(), {"ids": [50]})
    reader = read_pdf(out)
    assert len(reader.pages) == 1
    text = all_text(reader)
    assert "DELIVERY RECEIPT" in text
    assert "NAME:" in text
    assert "VESPA GTS 300 SUPER TECH" in text
    assert "MD7100001" in text
    assert "310,000.00" in text
    assert "Customer" in text  # sub-report signature block rendered
    (tmp_path / "dr.pdf").write_bytes(out)


def test_dr_portrait_letter():
    out = make_renderer([dr_row()]).render(DELIVERY_RECEIPT_PRPT.read_bytes(), {"ids": [50]})
    page = read_pdf(out).pages[0]
    assert float(page.mediabox.width) == pytest.approx(612.0)
    assert float(page.mediabox.height) == pytest.approx(792.0)


def test_dr_overflow_repeats_page_header():
    rows = [dr_row(product_name="ITEM %03d" % i) for i in range(60)]
    out = make_renderer(rows).render(DELIVERY_RECEIPT_PRPT.read_bytes(), {"ids": [50]})
    reader = read_pdf(out)
    assert len(reader.pages) >= 2
    # page-header repeats on every page
    for page in reader.pages:
        assert "DELIVERY RECEIPT" in page.extract_text()


def test_dr_long_address_is_not_clipped():
    # min-height is a minimum: the engine renders all wrapped lines even when
    # the element is not dynamic-height (verified against the Java engine output)
    long_address = "108 Competence Drive, Carmelray Industrial Park 1 SEPZ, Canlubang Calamba 4028"
    rows = [dr_row(vendor_address=long_address)]
    out = make_renderer(rows).render(DELIVERY_RECEIPT_PRPT.read_bytes(), {"ids": [50]})
    text = all_text(read_pdf(out))
    assert "Canlubang Calamba 4028" in text


def test_dr_no_rows_still_renders():
    out = make_renderer([]).render(DELIVERY_RECEIPT_PRPT.read_bytes(), {"ids": []})
    reader = read_pdf(out)
    assert len(reader.pages) == 1
    assert "DELIVERY RECEIPT" in all_text(reader)


# ── sales invoice ───────────────────────────────────────────

def test_si_landscape():
    out = make_renderer([si_row(1)]).render(SALES_INVOICE_PRPT.read_bytes(), {"ids": [1]})
    page = read_pdf(out).pages[0]
    assert float(page.mediabox.width) == pytest.approx(792.0)
    assert float(page.mediabox.height) == pytest.approx(612.0)


def test_si_content_and_number_formats(tmp_path):
    out = make_renderer([si_row(7)]).render(SALES_INVOICE_PRPT.read_bytes(), {"ids": [7]})
    text = all_text(read_pdf(out))
    assert "SALES INVOICE" in text
    assert "PIAGGIO PHILIPPINES CORPORATION" in text
    assert "INV/2026/00007" in text
    assert "ACME Corp" in text
    # java default number format: grouping, trailing zeros dropped
    assert "49,107.14" in text
    assert "55,000" in text


def test_si_two_invoices_repeat_group_header():
    rows = [si_row(1), si_row(1, description="TOPBOX"), si_row(2)]
    out = make_renderer(rows).render(SALES_INVOICE_PRPT.read_bytes(), {"ids": [1, 2]})
    text = all_text(read_pdf(out))
    assert text.count("SALES INVOICE") == 2
    assert "INV/2026/00001" in text
    assert "INV/2026/00002" in text


# ── ap voucher ──────────────────────────────────────────────

def ap_row(**over):
    row = {
        "company_logo": None, "company_address": "9th Floor Arthaland Tower",
        "company_tin": "691-334-462-000", "invoice_name": "INV/2026/00208",
        "ref": "INV/2026/00208", "print_date": "07/31/2026", "inv_date": "07/31/2026",
        "payment_term": "Pay Immediately", "vendor_name": "Wheeltek Motor Sales Corp Vespa - Calamba",
        "vendor_address": "Km 50 Manila S Rd, Real, Calamba", "vendor_tin": "005-156-353-00119",
        "notes": " ", "acct_codes": "150000", "gl_account": "Trade Receivables - Third Parties",
        "debit": 427199.99, "credit": 0.0, "analytic": " ", "total": 427199.99,
    }
    row.update(over)
    return row


def test_ap_voucher_renders_with_subreport():
    from conftest import AP_VOUCHER_PRPT

    sub_rows = [{"mode_payment": "BANK OF AMERICA 60866011", "total_payment": "PHP 576,863.04"}]

    def execute_query(sql, params):
        if "mode_payment" in sql:
            return list(sub_rows)
        return [ap_row(), ap_row(acct_codes="226012", gl_account="Output VAT Payable",
                                 debit=0.0, credit=45771.43)]

    out = NativeRenderer(execute_query).render(AP_VOUCHER_PRPT.read_bytes(), {"ids": [1]})
    text = all_text(read_pdf(out))
    assert "AP Voucher" in text
    assert "Bill Total:" in text
    assert "BANK OF AMERICA" in text                    # sub-report content
    assert "60866011" in text                           # (wraps in its 106pt box)
    assert "PHP 576,863.04" in text


def test_subreport_query_executes_once():
    from conftest import AP_VOUCHER_PRPT

    seen = []

    def execute_query(sql, params):
        seen.append(sql)
        if "mode_payment" in sql:
            return [{"mode_payment": "CASH", "total_payment": "PHP 1.00"}]
        return [ap_row()]

    NativeRenderer(execute_query).render(AP_VOUCHER_PRPT.read_bytes(), {"ids": [1]})
    sub_calls = [s for s in seen if "mode_payment" in s]
    assert len(sub_calls) == 1, "sub-report SQL ran %d times" % len(sub_calls)
    assert len(seen) == 2  # main query once, sub-report query once


def test_bir_2307_renders_background_image():
    from conftest import BIR_2307_PRPT

    out = make_renderer([{}]).render(BIR_2307_PRPT.read_bytes(),
                                     {"ids": [1], "partner_id": 1})
    reader = read_pdf(out)
    page = reader.pages[0]
    assert float(page.mediabox.width) == pytest.approx(612.0)
    assert float(page.mediabox.height) == pytest.approx(920.0)
    # the scanned form must be embedded as an image xobject
    xobjects = page["/Resources"].get("/XObject", {})
    assert any(x.get_object().get("/Subtype") == "/Image" for x in xobjects.values())
