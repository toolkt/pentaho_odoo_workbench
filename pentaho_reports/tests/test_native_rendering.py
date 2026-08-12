import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNativeRendering(TransactionCase):
    """.prpt reports render in-process — no external server involved."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env["ir.actions.report"]

    def _render(self, report_name, res_ids, data=None):
        report = self.Report.search([("report_name", "=", report_name)], limit=1)
        self.assertTrue(report, "report action %s missing" % report_name)
        return self.Report.render_report(
            report.id, res_ids, data or {"report_type": "pentaho"}
        )

    def test_delivery_receipt_renders_pdf(self):
        picking = self.env["stock.picking"].search([("state", "=", "done")], limit=1)
        if not picking:
            self.skipTest("no done picking in this database")
        output, output_type, filename, direct_print = self._render(
            "piaggio.delivery.receipt", [picking.id]
        )
        self.assertEqual(output_type, "pdf")
        self.assertTrue(base64.b64decode(output).startswith(b"%PDF"))

    def test_sales_invoice_renders_pdf(self):
        move = self.env["account.move"].search(
            [("move_type", "=", "out_invoice"), ("state", "=", "posted")], limit=1
        )
        if not move:
            self.skipTest("no posted customer invoice in this database")
        output, output_type, _filename, _direct = self._render(
            "piaggio.sales.invoice", [move.id]
        )
        self.assertEqual(output_type, "pdf")
        self.assertTrue(base64.b64decode(output).startswith(b"%PDF"))

    def test_non_pdf_output_is_rejected(self):
        picking = self.env["stock.picking"].search([("state", "=", "done")], limit=1)
        if not picking:
            self.skipTest("no done picking in this database")
        with self.assertRaises(UserError):
            self._render(
                "piaggio.delivery.receipt",
                [picking.id],
                {"report_type": "pentaho", "output_type": "xlsx"},
            )
