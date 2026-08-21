# -*- coding: utf-8 -*-
"""HTTP layer: /pentaho/preview (JSON-RPC, gated to report authors),
/pentaho/download and /pentaho/print (PDF replay; fileToken cookie contract
that Odoo 11-14's session.get_file depends on).

Version-agnostic: posts JSON through the raw requests session (works on 11+),
feature-detects the res.users groups field name (group_ids on 19).
"""
import base64
import json
import os

import odoo
from odoo.tests.common import HttpCase

try:  # Odoo >= 12
    from odoo.tests import tagged
except ImportError:  # Odoo 11
    def tagged(*tags):
        return lambda cls: cls

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'partner_list.prpt')


@tagged('post_install', '-at_install')
class TestPentahoControllers(HttpCase):

    def setUp(self):
        super(TestPentahoControllers, self).setUp()
        with open(FIXTURE, 'rb') as f:
            self.prpt_b64 = base64.b64encode(f.read()).decode()
        self.partner_ids = self.env['res.partner'].search([], limit=2, order='id').ids

    # ── helpers ────────────────────────────────────────────────────────

    def _url(self, path):
        # http_port is the config key on every version (the CLI flag was --xmlrpc-port before 12)
        return 'http://127.0.0.1:%s%s' % (odoo.tools.config['http_port'], path)

    def _groups_field(self):
        return 'group_ids' if 'group_ids' in self.env['res.users']._fields else 'groups_id'

    def _make_user(self, login, *group_xmlids):
        vals = {
            'name': login, 'login': login, 'password': login,
            self._groups_field(): [(6, 0, [self.env.ref(x).id for x in group_xmlids])],
        }
        return self.env['res.users'].create(vals)

    def _raw_call(self, params):
        resp = self.opener.post(self._url('/pentaho/preview'), json={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': params})
        return resp.json()

    def _call(self, params):
        body = self._raw_call(params)
        self.assertNotIn('error', body, body.get('error'))
        return body['result']

    def _preview_params(self):
        return {'prpt_b64': self.prpt_b64, 'model': 'res.partner', 'ids': self.partner_ids, 'variables': {}}

    # ── /pentaho/preview: positive ─────────────────────────────────────

    def test_preview_renders_pdf_for_admin(self):
        self.authenticate('admin', 'admin')
        result = self._call(self._preview_params())
        self.assertNotIn('error', result, result.get('error'))
        self.assertTrue(base64.b64decode(result['pdf_b64']).startswith(b'%PDF'))

    def test_preview_allows_report_author_without_admin(self):
        user = self._make_user('pentaho_author', 'base.group_user', 'base.group_system')
        self.assertFalse(user.share)
        self.authenticate('pentaho_author', 'pentaho_author')
        result = self._call(self._preview_params())
        self.assertTrue(base64.b64decode(result['pdf_b64']).startswith(b'%PDF'))

    # ── /pentaho/preview: the access gate ──────────────────────────────

    def _assert_access_error(self, body):
        self.assertIn('error', body, 'caller must not reach the render path')
        data = body['error'].get('data', {})
        self.assertIn('AccessError', '%s %s' % (data.get('name'), data.get('exception_type')))

    def test_preview_rejects_portal_user(self):
        user = self._make_user('pentaho_portal', 'base.group_portal')
        self.assertTrue(user.share)
        self.authenticate('pentaho_portal', 'pentaho_portal')
        self._assert_access_error(self._raw_call({'prpt_b64': 'eA==', 'model': False, 'ids': [], 'variables': {}}))

    def test_preview_rejects_internal_user_without_technical_access(self):
        user = self._make_user('pentaho_notech', 'base.group_user')
        self.assertFalse(user.share)
        self.authenticate('pentaho_notech', 'pentaho_notech')
        self._assert_access_error(self._raw_call({'prpt_b64': 'eA==', 'model': False, 'ids': [], 'variables': {}}))

    # ── /pentaho/preview: safe errors ──────────────────────────────────

    def test_preview_invalid_prpt_returns_safe_error(self):
        self.authenticate('admin', 'admin')
        result = self._call({'prpt_b64': base64.b64encode(b'not a real prpt').decode(),
                             'model': False, 'ids': [], 'variables': {}})
        self.assertIn('error', result)
        self.assertNotIn('Traceback', result['error'])
        self.assertNotIn('File "', result['error'])

    # ── /pentaho/download and /pentaho/print ───────────────────────────

    def _payload(self):
        return json.dumps([base64.b64encode(b'%PDF-1.4 fake').decode(), 'pdf', 'unit_test_report'])

    def test_download_replays_pdf_and_sets_file_token_cookie(self):
        self.authenticate('admin', 'admin')
        resp = self.opener.get(self._url('/pentaho/download'),
                               params={'data': self._payload(), 'token': '424242'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Content-Type'), 'application/pdf')
        self.assertIn('unit_test_report.pdf', resp.headers.get('Content-Disposition', ''))
        self.assertTrue(resp.content.startswith(b'%PDF'))
        self.assertEqual(resp.cookies.get('fileToken'), '424242',
                         'legacy session.get_file polls this cookie to unblock the UI')

    def test_print_returns_inline_pdf(self):
        self.authenticate('admin', 'admin')
        resp = self.opener.get(self._url('/pentaho/print'), params={'data': self._payload()})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Content-Type'), 'application/pdf')
        self.assertIn('inline', resp.headers.get('Content-Disposition', ''))

    def test_download_requires_login(self):
        # self.opener is a fresh cookie jar every setUp and nothing in this
        # test calls self.authenticate(), so as long as we do not reuse a
        # session_id cookie from another test this is a genuinely anonymous
        # request. Unlike a bare requests.Session(), self.opener also carries
        # whatever the test harness itself requires to reach the dispatcher
        # (Odoo >= 16's Opener.request() injects a required test-only cookie
        # per call, see odoo.tests.common.HttpCase.allow_requests) — a caller
        # with none of that harness plumbing 400s before auth='user' even
        # runs, which would falsely "pass" this test for the wrong reason.
        self.opener.cookies.clear()
        resp = self.opener.get(self._url('/pentaho/download'),
                               params={'data': self._payload()}, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303, 401, 403, 404),
                      'auth="user" route must not serve anonymous callers')
