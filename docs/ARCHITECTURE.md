# Architecture

## Intention

Clients run Pentaho Report Designer `.prpt` reports from inside Odoo. The original
solution (willowit's `Pentaho-reports-for-OpenERP`) needed a Java report server —
impossible on Odoo.sh and painful everywhere else. This repo solves it twice over:

1. a **pure-Python engine** that parses and renders `.prpt` bundles to PDF with
   reportlab (the 2026-08-12 fidelity port — see `PORT_CHANGES.md`: 1582/1639 real
   reports render, ~96.5%), and
2. **one module per Odoo version** (`v11` … `v19`) so the same engine ships to every
   client regardless of their Odoo, each folder self-contained and Odoo.sh-friendly
   (copy the folder to the root of an Odoo.sh repo).

## Component map

- **Engine** (`engine/native/`, Odoo-independent, Python ≥ 3.6):
  - `bundle.py` — unzips the `.prpt`, parses `layout.xml`/`datasources/sql-ds.xml`/
    styles into `model.py` records (`Element`, `Band`, `Group`, `Style`, `PageDef`,
    `PlainParameter` — plain classes with a `_Record` base, not dataclasses).
  - `renderer.py` — band/group flow: partitions rows, emits headers/details/footers,
    handles nested `group-body` groups and sub-reports.
  - `painter.py` — reportlab drawing: fonts, wrapping, borders, images, barcodes.
  - `query.py` — `${param}` placeholder → psycopg2 parameters; the report's
    `static-query` runs on **Odoo's own cursor** (the JDBC block in the `.prpt` is
    never used — which is why fixtures can be credential-scrubbed).
  - `fonts.py`, `formats.py` — font resolution and Java `SimpleDateFormat`/number
    format masks.
- **Glue** (`vNN/pentaho_reports/`): `models/ir_actions_report.py` (report type
  `pentaho`, prpt file storage, render entry points), `controllers/main.py`
  (`/pentaho/preview|download|print`), `views/report_views.xml`, the JS action
  handler, per-version tests, `migrations/NN.0.2.0.0/`.
- **Tools** (`tools/`): sync/drift for the engine copies, fixture scrubbing, and the
  three test harnesses (see Verification).

## The three families (definitive, grep-verified)

| Cell | A: v11 | A: v12–v13 | A: v14 | B: v15 | B: v16 | C: v17–v18 | C: v19 |
|---|---|---|---|---|---|---|---|
| JS file | `action_manager.js` | `action_manager.js` | `action_manager.js` | `action_service.js` | `action_service.js` | `action_service.js` | `action_service.js` |
| JS mechanism | `odoo.define` + include on `report.report` | `odoo.define` + `ActionManager.include` | same | `@odoo-module`, `registry.category("ir.actions.report handlers")` | same | same | same |
| `_t` source | `require('web.core')` | same | same | `env._t` | `env._t` | `import { _t } from "@web/core/l10n/translation"` | same |
| assets | `views/assets.xml` | same | same | manifest `'assets'` | same | same | same |
| view syntax | `attrs=` | `attrs=` | `attrs=` | `attrs=` | `attrs=` | python expressions | python expressions |
| preview route | `type='json'` | `type='json'` | `type='json'` | `type='json'` | `type='json'` | `type='json'` | `type='jsonrpc'` |
| `selection_add` `ondelete` | absent | absent | present | present | present | present | present |
| `create` decorator | `@api.model` (single vals) | `@api.model_create_multi` | same | same | same | same | same |
| dispatch hook | `render_pentaho(res_ids)` | `render_pentaho(res_ids)` | `_render_pentaho(res_ids)` | `_render_pentaho(res_ids)` | `_render_pentaho(report_ref, res_ids)` | same | same |
| notification | `do_notify`/`do_warn` | same | `displayNotification` (13 too) | `services.notification` | same | same | same |
| error idiom | jQuery Deferred `(error, event)` fail + `event.preventDefault()` | same (12) / Promise `.catch` (13) | Promise `.catch` + `errorMessage()` | OWL handler | same | same | same |

(Verify any cell: `grep -l jsonrpc v*/pentaho_reports/controllers/main.py` → v19 only;
`grep -L ondelete v*/pentaho_reports/models/ir_actions_report.py` → v11–v13;
`ls v*/pentaho_reports/static/src/js/` → `action_manager.js` on 11–14,
`action_service.js` on 15–19.)

Shared by every version: `render_report(report_id, res_ids, data)` (the JS entry
point, stable name + arity everywhere) and `_render_pentaho_report(res_ids,
data=None)` (the model-side core that invokes the engine); the per-version dispatch
hooks above are thin aliases Odoo's generic report machinery calls.

## Data flow of a print

1. User hits Print → Odoo emits an `ir.actions.report` action with
   `report_type: "pentaho"`.
2. The family's JS handler intercepts it, resolves the report **by `report_name`**,
   and calls `render_report` over RPC.
3. `render_report` → `_render_pentaho_report` → `NativeRenderer(execute_query)`
   parses the prpt, runs its `static-query` on Odoo's cursor with the record ids,
   paints the PDF, returns base64 + output type + filename + direct-print flag.
4. Download goes through `/pentaho/download` — on the legacy family via
   `session.get_file`, whose completion contract is the **`fileToken` cookie** the
   route must set (v11 polls it; v12+ use XHR completion). Direct print uses
   Print.js (`print_min.js`) via `/pentaho/print`.

## Verification strategy

- **Engine pytest** (`engine/native/tests`, also synced into every module):
  fixture-driven — scrubbed real reports (calibration layouts, sub-reports, nested
  groups, date masks, code128 barcodes, background images) plus the synthetic
  `partner_list.prpt` (evergood layout re-pointed at `res_partner`) that the Odoo
  module tests install and render. Absent fixtures SKIP, never error.
- **Engine matrix** (`tools/engine_matrix.sh`): the suite under every
  (Python, reportlab) pair the nine Odoo venvs ship — py3.6×rl3.5.59,
  py3.9×{3.5.59, 4.4.10, 5.0.0}, py3.10×3.6.8, py3.12×4.1.0. Venvs are cached with a
  `.ready` sentinel; a PIP failure removes the venv (no false PASS).
- **Module tests** (per `vNN/.../tests/`): version-agnostic by construction —
  `tagged` fallback for Odoo 11 (its at-install slot is demo-gated), `group_ids` vs
  `groups_id` detection (renamed in 19), JSON posted via `self.opener` (16+ test
  mode 400s foreign sessions), dispatch-shape detection, `fileToken` cookie assert.
- **Install harness** (`tools/odoo_install_test.sh NN`): createdb → `odoo-bin -i
  pentaho_reports --test-enable` on port `180NN` → scan the log for failures →
  dropdb (always, also on failure). PASS = module installed AND tests ran clean.
- **Acceptance** (`tools/test_matrix.sh`): drift → per-folder compileall with that
  Odoo's interpreter (+ engine on py3.6) → engine matrix → nine installs. 21 rows.

## Environment matrix

| Odoo | venv Python | reportlab | Harness specifics |
|---|---|---|---|
| 11 | 3.6.8 | 3.5.59 | `--limit-memory-hard=0` (Darwin), PIL shim, tagged fallback, `cr.commit()` in user fixture |
| 12 | 3.9 | 5.0.0 | `--limit-memory-hard=0`, PIL shim (`tools/pil_compat` via PYTHONPATH — Pillow ≥10 removed `Image.ANTIALIAS`) |
| 13 | 3.9 | 4.4.10 | `--limit-memory-hard=0`, `--test-tags` |
| 14 | 3.9 | 3.5.55 (installed by the plan — venv shipped broken) | `--limit-memory-hard=0` |
| 15 | 3.9 | 3.5.59 | `--limit-memory-hard=0`, longpolling port |
| 16 | 3.9 | 3.5.59 | test-request-key cookie via `self.opener` |
| 17 | 3.10 | 3.6.8 | gevent port |
| 18 | 3.12 | 4.1.0 | |
| 19 | 3.12 | 4.1.0 | `jsonrpc` route, `group_ids` |

## Known limits / out of scope

From the fidelity port's long tail (~3.5% of the 1,639-report corpus): crosstab
pivots, `style-expression` formulas, `list-parameter` prompts, corrupt zips, stale
absolute-path image resources. Python 3.5 (the `odoo:11` Docker image) is
deliberately unsupported — the floor is 3.6 (`engine/native/COMPAT.md`).
