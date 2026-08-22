"""partner_list.prpt: the synthetic fixture the Odoo module tests install and render.
It must parse, reference only `res_partner`, and render stub rows to a PDF."""
from conftest import PARTNER_LIST_PRPT

from native.bundle import PrptBundle
from native.renderer import NativeRenderer


def test_partner_list_query_targets_res_partner_only():
    bundle = PrptBundle.from_bytes(PARTNER_LIST_PRPT.read_bytes())
    sql = bundle.sql.lower()
    assert "from res_partner" in sql
    assert "sale_order" not in sql
    assert "${ids}" in bundle.sql


def test_partner_list_renders_pdf_with_stub_rows():
    calls = []

    def execute_query(sql, params):
        calls.append((sql, params))
        return [{"so_no": 1, "partner": "Azure Interior"}, {"so_no": 2, "partner": "Deco Addict"}]

    out = NativeRenderer(execute_query).render(PARTNER_LIST_PRPT.read_bytes(), {"ids": [1, 2]}, "pdf")
    assert out.startswith(b"%PDF")
    assert len(calls) == 1
    assert "res_partner" in calls[0][0]
