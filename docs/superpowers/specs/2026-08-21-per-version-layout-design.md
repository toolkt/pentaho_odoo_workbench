# `pentaho_reports` for Odoo 11 → 19: per-version layout — design

**Date:** 2026-08-21
**Repo:** `toolkt/pentaho_odoo_workbench`
**Status:** approved design, pending implementation plan

## 1. Goal

Ship the pure-Python Pentaho `.prpt` renderer (`pentaho_reports`, no Java / no Tomcat / no external service) as **one installable Odoo module per Odoo major version, 11 through 19**, laid out as version folders:

```
v11/pentaho_reports/   v12/pentaho_reports/   …   v19/pentaho_reports/
```

Each folder is a complete, self-contained module. A consumer copies the folder (or points `--addons-path` at `vNN/`) and installs it on that Odoo version.

"Works on all versions" is defined by the verification matrix in §7 — it is measured, not asserted.

## 2. Decisions already made

| Decision | Choice | Why |
|---|---|---|
| Deployment shape | **Folders only** (`vNN/pentaho_reports`) | What the user asked for; self-hosted `--addons-path` and copy-into-own-repo both work. Odoo.sh only auto-loads modules at a repository root, so Odoo.sh users copy the folder into their own repo; per-version branches are explicitly out of scope. |
| Engine strategy | **One engine, nine byte-identical copies** | The `native/` engine (~3,400 lines) has no Odoo dependency. One canonical copy + a sync script + a drift test means a render bug is fixed once. Real copies, not symlinks: GitHub zip downloads and `cp` break symlinks. |
| Python floor | **3.6** | Odoo 11's local venv is Python 3.6.8; Odoo 13/14 officially require ≥3.6. Python 3.5 (official floor of Odoo 11/12; the `odoo:11` Docker image) is an informed exclusion: EOL since 2020, and a materially larger rewrite. Documented in every manifest/README. |
| End-to-end check | Throwaway databases `pentaho_test_v11` … `pentaho_test_v19` on the local Postgres, dropped afterwards | Only way to prove install + render on each real Odoo. |

Python versions the matrix actually runs against (local venvs): v11 → 3.6.8, v12–v16 → 3.9, v17 → 3.10, v18–v19 → 3.12. Official `python_requires`: 11/12 ≥3.5, 13/14 ≥3.6, 15/16 ≥3.7, 17–19 ≥3.10.

reportlab shipped by each local venv: v11 3.5.59, v12 5.0.0, v13 4.4.10, v14 *missing (broken venv — install Odoo 14's pinned version first)*, v15/16 3.5.59, v17 3.6.8, v18/19 4.1.0. The engine uses only `canvas`, `pdfmetrics`/`TTFont`, `colors`, `ImageReader`, `createBarcodeDrawing` — an API slice stable across 3.5 → 5.0, to be proved by the matrix.

## 3. Repository layout

```
pentaho_odoo_workbench/
├── README.md                       version × Python × reportlab matrix; install notes; floor statement
├── engine/                         container so the package keeps its import name `native`
│   └── native/                     THE canonical engine + its pytest suite (tests/ inside)
│       ├── __init__.py  bundle.py  fonts.py  formats.py  model.py  painter.py  query.py  renderer.py
│       └── tests/                  conftest.py + test_*.py (+ calibration.py)
├── fixtures/                       8 vendored, credential-scrubbed .prpt test fixtures (+ README)
├── tools/
│   ├── sync_native.py              engine/ → vNN/pentaho_reports/native/ for every N (byte-identical)
│   ├── check_drift.py              exit 1 if any vNN/…/native differs from engine/ (also a pytest)
│   ├── scrub_fixture.py            rewrite sql-ds.xml connection user/password/url → placeholders
│   └── test_matrix.sh              the full verification run (§7)
├── v11/pentaho_reports/            complete module, manifest version 11.0.2.0.0
├── v12/pentaho_reports/            … 12.0.2.0.0
│   …
├── v19/pentaho_reports/            … 19.0.2.0.0
└── docs/superpowers/specs/         this design + the per-version API survey
```

The existing top-level `pentaho_reports/` (the Odoo-19-only module) is **moved** to `v19/pentaho_reports/` (git mv, history preserved) and becomes the first of the nine. The sibling symlink `pentaho-report-designer/pentaho_reports` outside the repo is re-pointed to `v19/pentaho_reports`.

Each `vNN/pentaho_reports/` contains:

```
__init__.py  __manifest__.py
controllers/   models/   views/   static/   tests/   migrations/NN.0.2.0.0/post-migrate.py
native/        ← synced copy of engine/ (including native/tests/)
README.md      ← one paragraph: which Odoo, which Python floor, install command
```

## 4. The engine (`engine/`, Python 3.6 floor)

Behaviour is unchanged; only constructs above the 3.6 floor are rewritten:

- **`@dataclass` → plain classes.** The seven model classes (`BorderSide`, `Style`, `Element`, `Band`, `Group`, `PageDef`, `PlainParameter`) get a small shared `_Record` base providing keyword `__init__` with defaults, `__eq__` (field-wise), and `__repr__`. Mutable defaults (`dict`, `list`, nested `Style()`/`Band()`) are created per instance, mirroring `default_factory`. Existing tests that compare model objects keep passing.
- **`from __future__ import annotations` removed** from all seven modules. Annotations are therefore evaluated at import time, so `str | None` → `Optional[str]`, `list[str]` → `List[str]`, `dict[str, BorderSide]` → `Dict[str, BorderSide]`, forward references as strings (`"Group"`). Module-level `_arial_family: dict | None = None` → `Optional[dict]`.
- f-strings (3.6 OK) stay. Dict-ordering assumptions are fine on CPython 3.6 (insertion-ordered as an implementation detail) and guaranteed from 3.7.
- A `engine/COMPAT.md` (or README section) states the floor and the rule: *no syntax or stdlib API newer than Python 3.6 in `engine/`; `tools/test_matrix.sh` step 2 enforces it.*

### Fixtures

The committed engine tests reference eight `.prpt` files by paths outside the repo (`piaggio_reports/…`, `sample_prpt/…`) — 26 of 91 tests currently error with `FileNotFoundError`. Fix:

- Vendor the eight files into `fixtures/` under their test names: `delivery_receipt.prpt`, `sales_invoice.prpt`, `ap_voucher.prpt`, `BIR_2307.prpt`, `evergood_sale_report.prpt`, `gl_listing_nested.prpt`, `print_supplier_check.prpt`, `product_barcode.prpt` (sources: `sample_prpt/piaggio_odoo_sh__*.prpt`, `sample_prpt/evergood_minimart__sale_report.prpt`, `sample_prpt/amici_v11__gl_listing_hardcode_sample.prpt`, `sample_prpt/amici_v11__print_supplier_check.prpt`, `sample_prpt/frpic_v16__product_barcode.prpt`). Largest is 225 KB (BIR_2307); total < 300 KB.
- **Scrub credentials** with `tools/scrub_fixture.py`: every `sql-ds.xml` (root and sub-report) gets `user` → `demo`, `password` → empty, `url` → `jdbc:postgresql://localhost/demo`. The renderer ignores these properties, so tests are unaffected. The script rewrites the zip preserving every other part byte-for-byte and keeps `mimetype` as the first, stored entry. A pytest asserts no fixture contains `encrypted:` or a non-placeholder user.
- `conftest.py` resolves the fixtures directory in this order: `$PENTAHO_FIXTURES` env var → walk up from `__file__` looking for a `fixtures/` directory containing `delivery_receipt.prpt` → otherwise **skip** the fixture-dependent tests with a clear message (never `FileNotFoundError`). This works for `engine/tests/` and for every synced `vNN/pentaho_reports/native/tests/` inside the repo, and degrades gracefully in a copied-out module.

### Sync and drift

- `tools/sync_native.py`: deletes `vNN/pentaho_reports/native/`, copies `engine/native/` (excluding `__pycache__`, `.pytest_cache`) for each N in 11..19; also copies `fixtures/partner_list.prpt` → `vNN/pentaho_reports/tests/fixtures/partner_list.prpt`. Idempotent.
- `tools/check_drift.py`: compares each copy to `engine/native/` (and the `partner_list.prpt` copies to `fixtures/`) file-by-file (names + bytes); prints the first difference; exit 1 on drift. Also exposed as `engine/tests/test_no_drift.py` (skips when not inside the repo).

## 5. Per-version glue — three families

The survey (`2026-08-21-odoo-version-api-survey.md`, with file:line evidence per version) shows exactly three shapes of glue. Everything not listed here is identical across all nine folders.

| Concern | **A: v11–v14** (legacy web client) | **B: v15–v16** | **C: v17–v19** |
|---|---|---|---|
| JS hook | `odoo.define` + `ActionManager.include`. v12–14 override `_executeReportAction` and `require('web.ReportActionManager')` for load order. v11 overrides `ir_actions_report` and `require('report.report')`. Unknown types are console-error + reject in core, so the override must come first in the include chain. | `/** @odoo-module **/`, `registry.category("ir.actions.report handlers").add(...)`, handler returns `true` when it handled the action | same as B |
| Download | `session.get_file({url, data, success, error, complete})` — POSTs FormData with `token` + `csrf_token`; the route **must set the `fileToken` cookie** (current controller already does) and return a non-HTML mimetype | `download({url, data})` from `@web/core/network/download` | same |
| Block UI / notify | `framework.blockUI()/unblockUI()`; v11–12 `this.do_notify/do_warn`; v13–14 `this.displayNotification({type,title,message})` | `env.services.ui.block()`, `env.services.notification.add(msg, {type})` | same |
| Translations in JS | `core._t` | `env._t` | `_t` from `@web/core/l10n/translation` |
| Assets | `views/assets.xml` template inheriting `web.assets_backend`, listed in manifest `data` | manifest `assets` key | same |
| Views | `attrs="{'invisible': [('report_type','!=','pentaho')], 'required': [...]}"` (Python-expression attrs fail view validation) | `attrs` | `invisible="report_type != 'pentaho'"` (`attrs` hard-rejected) |
| JSON route | `type='json'` | `'json'` | v17–18 `'json'`; **v19 `'jsonrpc'`** (`'json'` is a deprecated alias that warns) |
| `report_type` `selection_add` | v11–13: no `ondelete` (v13 ignores it) | `ondelete={'pentaho': 'set default'}` **required** (v14 too) | required |
| `create` | v11: `@api.model def create(self, vals)`; `@api.multi` on `write`/multi-record methods | `@api.model_create_multi` (v12+) | multi |
| Render dispatch alias | v11–13: `render_pentaho(self, res_ids, data=None)`; v14–15: `_render_pentaho(self, res_ids, data=None)` (recordset `self`) | | v16+: `@api.model _render_pentaho(self, report_ref, res_ids, data=None)` resolving via `self._get_report(report_ref)` |
| `_()` | single argument + `%` (already the module's style) | same | same |
| `config['addons_path']` | comma-joined `str` | `str` | v19 `list` (existing normalisation stays) |

Shared across all nine:
- The JS resolves the report **by `report_name`** (search on `ir.actions.report`) and calls the public ORM method `render_report(report_id, res_ids, data)` → `(content_b64, output_type, filename, direct_print)`. This sidesteps the v11–14 trap where `report_action()` dicts carry no `id`, and works identically on 15+.
- The dispatch alias above is a thin wrapper over the same internal `_render_pentaho_report(report, res_ids, data)` helper, so `report._render(...)` / `report.render(...)` also work where core supports it (mail-template attachment becomes possible on 16+ for free; not in scope to wire on 11–15).
- `/pentaho/download` and `/pentaho/print` stay `type='http'`, accept POST + `token=None, **kw`, set the `fileToken` cookie, return `application/pdf`.
- `/pentaho/preview` keeps its authorization gate (`not user.share and has_group('base.group_system')`) and its error contract (`{'error': ...}` / `{'pdf_b64': ...}`).
- Manifest: `'version': 'NN.0.2.0.0'`, `'depends': ['base', 'web']`, `'external_dependencies': {'python': ['reportlab']}`, license LGPL-3, author Toolkit Inc.; description gains a "Requirements: Python ≥ 3.6" line.
- `migrations/NN.0.2.0.0/post-migrate.py`: same content as today's 19.0.2.0.0 (drops the legacy Java-server `ir_config_parameter` keys) — the legacy willowit module existed on these versions too.

## 6. Module tests (per folder)

The committed `tests/test_native_rendering.py` depends on Piaggio-only report actions (`piaggio.delivery.receipt`, …) and would **fail** in a fresh database. Replaced by self-contained tests that ship in every folder:

- `tests/test_render.py` (TransactionCase): creates an `ir.actions.report` with `report_type='pentaho'`, `model='res.partner'`, `report_name='pentaho_reports.test_partner_list'`, and uploads `tests/fixtures/partner_list.prpt` — a small fixture derived from the simplest vendored report whose `static-query` is rewritten to `SELECT id, name, email FROM res_partner WHERE id IN (${ids}) ORDER BY id`, with layout fields bound to those columns. Asserts `render_report` returns `%PDF`, `output_type == 'pdf'`, the custom `variables.filename` path, and that a non-pentaho report raises `UserError`. Also asserts the per-version dispatch alias (`render`/`_render`) returns `(bytes, 'pdf')`.
- `tests/test_preview_controller.py` (HttpCase): `/pentaho/preview` returns `pdf_b64` for an internal `base.group_system` user, an `{'error': …}` (not a traceback) for a corrupt upload, and an `AccessError`-shaped JSON-RPC error for a portal/share user and for an internal user without `base.group_system`. JSON posting idiom per version: `self.make_jsonrpc_request` on 17+, `self.url_open(..., data=json.dumps(envelope), headers={'Content-Type': 'application/json'})` on 13–16, `self.opener.post(url, json=envelope)` on 11–12. v11 has no `tagged` decorator (tests run at install); 12+ use `@tagged('post_install', '-at_install')`.
- `native/tests/` (the synced engine suite) is discoverable by pytest only; Odoo's test loader ignores it because it is not under `tests/`.

## 7. Verification matrix — `tools/test_matrix.sh`

Runs top to bottom, stops on first failure, prints a final table. This is the acceptance criterion for the whole project.

1. **Drift:** `tools/check_drift.py` — all nine `native/` copies identical to `engine/`.
2. **Syntax floor per folder:** `python -m compileall -q vNN/pentaho_reports` using **that version's venv interpreter** (`/Volumes/Workspace/Development/OdooWorkbench/odooNN/venv/bin/python`), plus `engine/` with Python 3.6.8 explicitly.
3. **Engine tests across interpreters × reportlab pins**, in scratch venvs under the session scratchpad (never touching the Odoo venvs): py3.6 + reportlab 3.5.59 (+ pytest 7.0.x, pypdf 3.x — pypdf is a test-only dependency; the engine itself never imports it); py3.9 + 3.5.59; py3.9 + 4.4.10; py3.9 + 5.0.0; py3.10 + 3.6.8; py3.12 + 4.1.0. Each runs `pytest engine/tests` — all pass, none skipped for missing fixtures.
4. **Install + module tests on every Odoo:** for N in 11..19:
   `odooNN/venv/bin/python odooNN/odoo/odoo-bin -d pentaho_test_vNN --addons-path=odooNN/odoo/addons,odooNN/enterprise,<repo>/vNN -i pentaho_reports --test-enable --stop-after-init --log-level=test` (`--test-tags /pentaho_reports` on 12+; Odoo 11 has no `--test-tags`, so its run relies on `--test-enable` alone and the module's tests being the only new ones installed). Pass = exit 0 and no `ERROR`/`FAIL`/`Traceback` lines for `pentaho_reports` in the log. Odoo 14's venv gets `pip install reportlab==3.5.55` (its `requirements.txt` pin for Python ≥ 3.8) first.
5. **Cleanup:** `dropdb pentaho_test_vNN` for all nine (also on failure, via trap).

Ports/DB roles: Postgres roles `odoo11`…`odoo19` exist locally; each run uses its own role via `--db_user`. HTTP port per run is set with `--http-port` to avoid colliding with running instances.

## 8. Documentation

- Root `README.md`: what the module is (pure-Python, Odoo.sh-friendly), the version table (folder → Odoo → Python floor → tested Python/reportlab), install instructions (copy folder / addons-path), the Python 3.6 floor and the Python 3.5 exclusion, how to run `tools/test_matrix.sh`, and the sync/drift rule for contributors.
- Per-folder `README.md`: one paragraph pointing back to root plus the exact install command for that version.
- `PORT_CHANGES.md` moves to `docs/` unchanged (history of the fidelity port).

## 9. Out of scope (recorded, not built)

- Odoo.sh per-version branches / a publish script.
- Python 3.5 support.
- mail.template "attach report" for pentaho on Odoo 11–15 (core raises for non-qweb types there).
- Engine feature gaps already logged: crosstabs, `style-expression` formulas, `list-parameter`.
- Live-Odoo manual verification of the desktop designer's preview button against every version (the HttpCase covers the endpoint contract).

## 10. Risks and how the design handles them

| Risk | Mitigation |
|---|---|
| A reportlab API difference across 3.5 → 5.0 breaks rendering on one version | Matrix step 3 runs the corpus-backed engine tests against every pin actually shipped. |
| A copy of `native/` is edited directly and drifts | Drift test in step 1, runnable as pytest; README rule. |
| Legacy `session.get_file` never unblocks the UI | Route sets `fileToken` cookie and returns `application/pdf`; HttpCase asserts the cookie on 11–14. |
| Module tests depend on data not in a fresh DB | §6 replaces Piaggio-bound tests with a `res.partner` fixture. |
| Credentials in fixtures | Scrubbed by tool + asserted by test. |
| Odoo 19 `type='json'` deprecation becomes removal | v19 uses `'jsonrpc'` now. |
