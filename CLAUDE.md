# CLAUDE.md — how to work in this repository

## What this repo is

`pentaho_reports`: render Pentaho Report Designer `.prpt` files to PDF **inside Odoo
with a pure-Python engine** — no Java, no Tomcat, no external report server, so it runs
anywhere Odoo runs, including Odoo.sh. Shipped as nine self-contained per-version
folders `v11/pentaho_reports` … `v19/pentaho_reports` sharing one canonical engine.

## Layout

- `engine/native/` — the ONE canonical renderer (`bundle.py` parser, `model.py`,
  `renderer.py`, `painter.py`, `query.py`, `fonts.py`, `formats.py`) + its pytest suite.
- `vNN/pentaho_reports/` — per-version module: `models/ir_actions_report.py`,
  `controllers/main.py`, `views/report_views.xml` (+ `views/assets.xml` on 11–14),
  `static/src/js/`, `migrations/NN.0.2.0.0/`, `tests/`, and a synced `native/` copy.
- `fixtures/` — credential-scrubbed real `.prpt` test files (+ synthetic `partner_list.prpt`).
- `tools/` — `sync_native.py`, `check_drift.py`, `scrub_fixture.py`, `engine_matrix.sh`,
  `odoo_install_test.sh`, `test_matrix.sh`, `pil_compat/` (harness-only shim).
- `docs/` — `ARCHITECTURE.md`, `ADDING-A-VERSION.md`, `DECISIONS.md`, `LESSONS.md`,
  `HISTORY.md`, `PORT_CHANGES.md`, `build-log/`, `superpowers/{specs,plans}/`.

## The three rules

1. **Engine code is edited ONLY in `engine/native/`.** Every `vNN/pentaho_reports/native/`
   is a byte-identical copy made by `python3 tools/sync_native.py`;
   `python3 tools/check_drift.py` (and a pytest) must pass. Never hand-edit a copy.
2. **The engine's Python floor is 3.6** (`engine/native/COMPAT.md`) — Odoo 11 runs on
   3.6.8. No dataclasses, no `from __future__ import annotations`, no `X | None`,
   no `list[str]` in evaluated annotations. v11's glue must also be 3.6-clean.
3. **Glue comes in three families** (full table in `docs/ARCHITECTURE.md`):

| | A: v11–v14 (legacy web client) | B: v15–v16 (OWL) | C: v17–v19 (OWL + py-expr views) |
|---|---|---|---|
| JS | `action_manager.js`, `odoo.define` + include (`report.report` on 11, `ActionManager` on 12–14) | `action_service.js`, `@odoo-module` + `registry.category("ir.actions.report handlers")` | same as B |
| assets | XML `views/assets.xml` (`web.assets_backend`) | manifest `'assets'` | manifest `'assets'` |
| view attrs | `attrs=` | `attrs=` | python expressions |
| preview route | `type='json'` | `type='json'` | `'json'` (17–18) / **`'jsonrpc'` (19)** |
| dispatch alias | `render_pentaho(res_ids)` (11–13) / `_render_pentaho(res_ids)` (14) | `_render_pentaho(res_ids)` (15) / `(report_ref, res_ids)` (16) | `_render_pentaho(report_ref, res_ids)` |
| create | `@api.model` `create(vals)` on 11; `@api.model_create_multi` 12+ | model_create_multi | model_create_multi |
| `selection_add` `ondelete` | absent 11–13, required 14 | required | required |
| notification | `do_notify`/`do_warn` (11–12), `displayNotification` (13–14) | `services.notification` | `services.notification` |
| error idiom | jQuery Deferred `(error, event)` + `preventDefault` (11–12); Promise `.catch` + `errorMessage()` (13–14) | OWL handler | OWL handler |

Every version also has the shared core: `render_report(report_id, res_ids, data)` →
`_render_pentaho_report(res_ids, data=None)` → `NativeRenderer`.

## How to verify

- Engine only: `python -m pytest` from the repo root (canonical suite via `pytest.ini`).
- Cross-interpreter: `tools/engine_matrix.sh` (Python 3.6/3.9/3.10/3.12 × reportlab 3.5–5.0).
- One Odoo: `tools/odoo_install_test.sh NN` — installs into throwaway DB `pentaho_test_vNN`
  (created `createdb -O odooNN`, always dropped), runs the module tests, scans the log.
- Everything: `tools/test_matrix.sh` — the acceptance run (drift → compileall per venv →
  engine matrix → nine installs). All 21 rows must PASS.
- Assumed local paths: `/Volumes/Workspace/Development/OdooWorkbench/odooNN/{odoo,venv}`,
  Postgres roles `odoo11`…`odoo19` (trust, no CREATEDB), ports 180NN free.

## How to change things

- **Engine change:** edit `engine/native/` → pytest → `tools/sync_native.py` →
  `tools/check_drift.py` → `tools/test_matrix.sh`.
- **Glue change:** edit the family's reference first — v19 for 17–19, v16 for 15–16,
  v14 for 12–14, v11 alone — then replay to the siblings and re-run each sibling's
  `tools/odoo_install_test.sh NN`. Family differences are deliberate; check the table
  before assuming a sibling is identical.
- **New Odoo version:** follow `docs/ADDING-A-VERSION.md` end to end.

## Conventions

- `_('…%s') % x` — single-argument `_()` only (Odoo 11–13 raise on two-arg).
- macOS: BSD `sed -i ''`; bash 3.2 — guard empty arrays with `${arr[@]+"${arr[@]}"}`.
- Fixtures committed to the repo must be credential-scrubbed via `tools/scrub_fixture.py`
  (a pytest enforces it). Never commit a raw client `.prpt`.
- Don't reformat files you did not otherwise change; no repo-wide formatters.
- Commit trailer: `Co-Authored-By: Claude … <noreply@anthropic.com>` (+ session link).

## Where the memory lives

`docs/HISTORY.md` (timeline), `docs/DECISIONS.md` (every decision + why),
`docs/LESSONS.md` (gotchas: symptom → cause → fix), `docs/build-log/` (the verbatim
build ledger and per-task reports with the exact commands that proved each step).
