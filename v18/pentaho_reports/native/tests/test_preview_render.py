"""Render an uploaded .prpt via NativeRenderer directly — the core path the
``/pentaho/preview`` controller wraps (see ../../controllers/main.py).

No Odoo import here: this proves the bytes-in, PDF-out contract the
controller depends on, runnable outside a live Odoo. The controller's own
auth/HTTP wiring is exercised separately by
``pentaho_reports/tests/test_preview_controller.py`` (an Odoo HttpCase,
runnable only inside Odoo).
"""
import pytest

from conftest import EVERGOOD_SALE_REPORT_PRPT

from native.renderer import NativeRenderer

# a small, real-world .prpt: two text-fields bound to a two-column query,
# no group, no sub-report — good enough to prove the render path without
# pulling in the heavier calibration fixtures
SALE_REPORT_PRPT = EVERGOOD_SALE_REPORT_PRPT


def test_preview_render_produces_pdf_from_uploaded_bytes():
    """Same call shape the controller makes: raw .prpt bytes + a parameters
    dict with ids/user/lang/tz, output_type='pdf' → PDF bytes."""
    rows = [
        {"so_no": "SO0001", "partner": "Acme Corp"},
        {"so_no": "SO0002", "partner": "Wayne Enterprises"},
    ]

    def stub_execute_query(sql, params):
        assert "so.id in" in sql
        assert params == [1, 2]
        return rows

    parameters = {
        "ids": [1, 2],
        "user_id": 2,
        "user_name": "Mitchell Admin",
        "context_lang": "en_US",
        "context_tz": "UTC",
    }

    pdf = NativeRenderer(stub_execute_query).render(
        SALE_REPORT_PRPT.read_bytes(), parameters, "pdf")

    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 0


def test_preview_render_handles_zero_rows():
    """No matching records → still a valid single-page PDF, not an error."""
    def stub_execute_query(sql, params):
        return []

    pdf = NativeRenderer(stub_execute_query).render(
        SALE_REPORT_PRPT.read_bytes(), {"ids": []}, "pdf")

    assert pdf.startswith(b"%PDF")
