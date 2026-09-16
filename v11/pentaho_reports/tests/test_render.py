# -*- coding: utf-8 -*-
"""In-process rendering through ir.actions.report — self-contained: installs its
own report record bound to res.partner with the partner_list.prpt fixture.

Version-agnostic: runs unchanged on Odoo 11 → 19 (see _tagged / _render_dispatch).
"""
import base64
import os

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

try:  # Odoo >= 12
    from odoo.tests import tagged
except ImportError:  # Odoo 11: no odoo.tests.tagged, but the test runner itself
    # already reads `post_install`/`at_install` class attributes directly
    # (odoo/modules/module.py:478-492 runs_at/runs_at_install/runs_post_install),
    # and --without-demo=all (our harness) makes the has_demo-gated at-install
    # slot in loading.py:183-210 a no-op, so untagged tests would never run at
    # all. Set the two attributes our tags map to so the post-install pass in
    # service/server.py:1067-1076 (module_names = registry.updated_modules,
    # position=runs_post_install) picks these classes up.
    def tagged(*tags):
        def decorator(cls):
            if 'post_install' in tags:
                cls.post_install = True
            if '-at_install' in tags:
                cls.at_install = False
            return cls
        return decorator

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'partner_list.prpt')


@tagged('post_install', '-at_install')
class TestPentahoRender(TransactionCase):

    def setUp(self):
        super(TestPentahoRender, self).setUp()
        with open(FIXTURE, 'rb') as f:
            self.prpt_b64 = base64.b64encode(f.read())
        self.Report = self.env['ir.actions.report']
        self.report = self.Report.create({
            'name': 'Pentaho Test Partner List',
            'report_name': 'pentaho_reports.test_partner_list',
            'model': 'res.partner',
            'report_type': 'pentaho',
            'pentaho_file': self.prpt_b64,
            'pentaho_filename': 'partner_list.prpt',
        })
        self.partners = self.env['res.partner'].search([], limit=3, order='id')
        self.assertTrue(self.partners, 'base always ships partners')

    def test_create_forces_action_type(self):
        self.assertEqual(self.report.type, 'ir.actions.report')
        self.assertEqual(self.report.pentaho_report_output_type, 'pdf')

    def test_render_report_returns_pdf_tuple(self):
        content_b64, output_type, filename, direct_print = self.Report.render_report(
            self.report.id, self.partners.ids, {})
        self.assertEqual(output_type, 'pdf')
        self.assertEqual(filename, 'pentaho_reports.test_partner_list')
        self.assertFalse(direct_print)
        self.assertTrue(base64.b64decode(content_b64).startswith(b'%PDF'))

    def test_render_report_custom_filename_strips_extension(self):
        _c, _t, filename, _d = self.Report.render_report(
            self.report.id, self.partners.ids, {'variables': {'filename': 'partners.pdf'}})
        self.assertEqual(filename, 'partners')

    def test_render_report_zero_rows_still_pdf(self):
        content_b64, _t, _f, _d = self.Report.render_report(self.report.id, [], {})
        self.assertTrue(base64.b64decode(content_b64).startswith(b'%PDF'))

    def test_render_report_rejects_non_pentaho_report(self):
        qweb = self.Report.search([('report_type', '=', 'qweb-pdf')], limit=1)
        if not qweb:
            self.skipTest('no qweb report in this database')
        with self.assertRaises(UserError):
            self.Report.render_report(qweb.id, self.partners.ids, {})

    def test_missing_file_raises_validation_error(self):
        from odoo.exceptions import ValidationError
        self.report.with_context(skip_load_file=True).write({'pentaho_file': False})
        with self.assertRaises(ValidationError):
            self.report._render_pentaho_report(self.partners.ids, {})

    def test_core_render_dispatch_finds_pentaho(self):
        """Odoo's generic render entry point must reach our renderer on every
        version: 11-13 `render()`, 14-15 `_render(res_ids)`, 16+ `_render(ref, res_ids)`."""
        Report = self.report
        if hasattr(Report, '_render') and 'report_ref' in Report._render.__code__.co_varnames:
            out = self.Report._render(Report.id, self.partners.ids)
        elif hasattr(Report, '_render'):
            out = Report._render(self.partners.ids)
        else:
            out = Report.render(self.partners.ids)
        self.assertIsNotNone(out, 'generic dispatch did not find the pentaho renderer')
        content, output_type = out
        self.assertEqual(output_type, 'pdf')
        self.assertTrue(content.startswith(b'%PDF'))

    def test_report_queries_keep_numeric_scale(self):
        # the Java engine reads NUMERIC as BigDecimal ("30.00"); Odoo's own
        # cursor turns it into a float, which must stay true outside reports
        rows = self.Report._pentaho_execute_query(
            "SELECT 30.00::numeric AS qty, %s::int AS n", [7])
        self.assertEqual(str(rows[0]['qty']), '30.00')
        self.assertEqual(rows[0]['n'], 7)
        self.env.cr.execute("SELECT 30.00::numeric")
        self.assertIsInstance(self.env.cr.fetchone()[0], float)
