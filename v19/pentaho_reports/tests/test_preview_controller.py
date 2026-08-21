# -*- coding: utf-8 -*-
import base64
import json
from pathlib import Path

from odoo.tests import HttpCase, tagged

MODULE_DIR = Path(__file__).resolve().parents[1]  # pentaho_reports/
SALE_REPORT_PRPT = MODULE_DIR.parent / "sample_prpt" / "evergood_minimart__sale_report.prpt"


@tagged("post_install", "-at_install")
class TestPreviewController(HttpCase):
    """/pentaho/preview renders an uploaded .prpt end to end, gated to
    report-author (Technical) access.

    Companion to native/tests/test_preview_render.py, which exercises the
    NativeRenderer core (bytes-in, PDF-out) directly and runs without a
    live Odoo. This file proves the HTTP/JSON-RPC wrapper around it:
    - auth='user' + base.group_system gate (report authors only — see
      controllers/main.py's preview_pentaho_report for why: the endpoint
      runs the raw SQL embedded in whatever .prpt bytes the caller posts,
      so auth='user' alone would let a portal/customer user run arbitrary
      SQL against the database),
    - base64 request/response handling,
    - render errors come back as a safe `{'error': ...}` payload rather
      than a 500 or a traceback.
    """

    def _raw_call(self, params):
        """POST to /pentaho/preview, return the parsed JSON-RPC envelope
        as-is (may contain a top-level 'error' if the call was rejected,
        e.g. by the access gate, before the handler ever returned)."""
        response = self.url_open(
            "/pentaho/preview",
            data=json.dumps({
                "jsonrpc": "2.0",
                "method": "call",
                "params": params,
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        return response.json()

    def _call(self, params):
        """Like _raw_call, but asserts the JSON-RPC call itself succeeded
        and returns the handler's `result` dict (which may still be an
        expected `{'error': ...}` payload, e.g. UnsupportedFeature)."""
        body = self._raw_call(params)
        self.assertNotIn("error", body, body.get("error"))
        return body["result"]

    @staticmethod
    def _placeholder_prpt_b64():
        # Content is irrelevant for the access-gate tests: an unauthorized
        # caller must be rejected before the bytes are ever decoded/parsed.
        return base64.b64encode(b"irrelevant, rejected before parsing").decode()

    # ── positive: report-author (base.group_system) access ─────────────

    def test_preview_renders_pdf(self):
        """Baseline: the DB's admin user (a report author) gets a PDF back."""
        if not SALE_REPORT_PRPT.exists():
            self.skipTest("sample .prpt fixture not present in this checkout: %s"
                          % SALE_REPORT_PRPT)

        self.authenticate("admin", "admin")
        prpt_b64 = base64.b64encode(SALE_REPORT_PRPT.read_bytes()).decode()

        result = self._call({
            "prpt_b64": prpt_b64,
            "model": "sale.order",
            "ids": [1],
            "variables": {},
        })

        self.assertNotIn("error", result, result.get("error"))
        self.assertIn("pdf_b64", result)
        pdf = base64.b64decode(result["pdf_b64"])
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_preview_allows_report_author_without_admin(self):
        """Positive control for the gate: an internal user who has
        base.group_system (but is not the superuser) must still succeed."""
        if not SALE_REPORT_PRPT.exists():
            self.skipTest("sample .prpt fixture not present in this checkout: %s"
                          % SALE_REPORT_PRPT)

        author_user = self.env["res.users"].create({
            "name": "Preview Report Author Test User",
            "login": "preview_author_test",
            "password": "preview_author_test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("base.group_system").id,
            ])],
        })
        self.assertFalse(author_user.share, "sanity: group_system must not be a portal group")
        self.authenticate("preview_author_test", "preview_author_test")

        prpt_b64 = base64.b64encode(SALE_REPORT_PRPT.read_bytes()).decode()
        result = self._call({
            "prpt_b64": prpt_b64,
            "model": "sale.order",
            "ids": [1],
            "variables": {},
        })

        self.assertNotIn("error", result, result.get("error"))
        pdf = base64.b64decode(result["pdf_b64"])
        self.assertTrue(pdf.startswith(b"%PDF"))

    # ── negative: the access gate must reject everyone else ────────────

    def test_preview_rejects_portal_user(self):
        """Portal/customer users are excluded: auth='user' alone is not
        internal-only, so the handler's explicit gate must reject them
        before any .prpt bytes are parsed or any SQL runs."""
        portal_user = self.env["res.users"].create({
            "name": "Preview Portal Test User",
            "login": "preview_portal_test",
            "password": "preview_portal_test",
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        self.assertTrue(portal_user.share, "sanity: portal users must be 'share' users")
        self.authenticate("preview_portal_test", "preview_portal_test")

        body = self._raw_call({
            "prpt_b64": self._placeholder_prpt_b64(),
            "model": False,
            "ids": [],
            "variables": {},
        })

        self.assertIn("error", body, "portal user must not reach the render path")
        self.assertEqual(
            body["error"].get("data", {}).get("name"),
            "odoo.exceptions.AccessError",
        )

    def test_preview_rejects_internal_user_without_technical_access(self):
        """An internal (non-share) user without base.group_system is not a
        report author and must also be rejected."""
        internal_user = self.env["res.users"].create({
            "name": "Preview No-Technical Test User",
            "login": "preview_notech_test",
            "password": "preview_notech_test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.assertFalse(internal_user.share, "sanity: this must be an internal user")
        self.authenticate("preview_notech_test", "preview_notech_test")

        body = self._raw_call({
            "prpt_b64": self._placeholder_prpt_b64(),
            "model": False,
            "ids": [],
            "variables": {},
        })

        self.assertIn(
            "error", body,
            "internal user without Technical (base.group_system) access must be rejected")
        self.assertEqual(
            body["error"].get("data", {}).get("name"),
            "odoo.exceptions.AccessError",
        )

    # ── render-error safety (unaffected by the gate) ────────────────────

    def test_preview_invalid_prpt_returns_safe_error(self):
        """Garbage bytes from an authorized caller must never surface a
        traceback or DB error text — only the access gate should raise;
        render failures come back as a `{'error': ...}` payload."""
        self.authenticate("admin", "admin")

        result = self._call({
            "prpt_b64": base64.b64encode(b"not a real prpt file").decode(),
            "model": False,
            "ids": [],
            "variables": {},
        })

        self.assertIn("error", result)
        self.assertNotIn("Traceback", result["error"])
        self.assertNotIn("File \"", result["error"])
