# Adding a new Odoo version (the v20 playbook)

Written so an agent with no other context can do it end to end. The worked history for
v11–v19 lives in `superpowers/specs/2026-08-21-odoo-version-api-survey.md` (per-version
API facts with file:line evidence) — reproduce that survey for the new version FIRST,
then copy the nearest sibling and adjust only what the survey says changed.

## 1. Survey the new Odoo first

Answer this questionnaire against the new version's source tree (grep starting points:
`odoo/http.py`, `odoo/fields.py`, `odoo/api.py`,
`addons/base/models/ir_actions_report.py`, `addons/base/models/ir_ui_view.py`,
`addons/web/static/src/webclient/actions/action_service.js`, `odoo/tests/common.py`,
`odoo/tools/config.py`, `setup.py`):

- Python floor (setup.py / release notes) and the local venv's actual interpreter.
- Report-action JS: what mechanism dispatches `ir.actions.report`? How do you
  intercept a custom `report_type`? Download helper? Block-UI? Notification API?
  ES-module support?
- Assets: manifest `'assets'` key or XML template?
- View conditional-attribute syntax (`attrs=` vs python expressions) + the form and
  search view xmlids the module inherits.
- HTTP: JSON route `type` value (`'json'`? `'jsonrpc'`?), `content_disposition`,
  `make_response` location.
- ORM: `model_create_multi`? `selection_add` `ondelete` required?
  `cr.savepoint()`? `addons_path` config type? `has_group` signature?
  `res.users.share` / `group_ids` vs `groups_id`? `_()` arity!
- Reports: report model name, `report_type` selection values, the generic render
  dispatch name + signature (`_render_<type>`?), Binary attachment default, report
  bindings mechanism.
- Tests: TransactionCase/HttpCase conventions, how to POST JSON in tests
  (test-request-key cookie?), `tagged` availability, the exact test-run command.

## 2. Copy the nearest family sibling

For v20 that is `v19` (family C). `cp -R v19/pentaho_reports v20/pentaho_reports`,
then delete the copied `native/` (the sync tool recreates it).

## 3. Mechanical edits

- `__manifest__.py`: `'version': '20.0.2.0.0'`.
- `migrations/19.0.2.0.0/` → `migrations/20.0.2.0.0/`.
- `vNN` README: version line.

## 4. Decision checklist (survey answer ≠ sibling behavior)

- Route type renamed again → change the decorator in `controllers/main.py` (v19's
  `jsonrpc` is exactly this: `'json'` became a deprecation alias).
- `res.users` group field renamed → the tests already detect `group_ids`/`groups_id`;
  extend the detector rather than hardcoding.
- Generic render dispatch signature changed → add the new hook shape AND extend
  `test_core_render_dispatch_finds_pentaho` to recognize it.
- View syntax changed → rewrite `views/report_views.xml` in the new syntax.
- The JS reads a new action field → the model may need it in `_get_readable_fields`.
- Notification/translation API moved → adjust `action_service.js` imports.

## 5. Wire the tooling

- `VERSIONS = list(range(11, 21))` in BOTH `tools/sync_native.py` and
  `tools/check_drift.py`.
- `tools/odoo_install_test.sh`: the new port is `18020`; add any version-specific
  flags the survey demands (see the case ladder for `--limit-memory-hard`,
  longpolling/gevent ports, PIL shim, `--test-tags`).
- `tools/test_matrix.sh`: extend both `for N in …` loops.
- `tools/engine_matrix.sh`: add the new (Python, reportlab) pair if the new venv
  ships one not already covered.
- Root `README.md` table + `CLAUDE.md` family table + `docs/ARCHITECTURE.md` tables.

## 6. Prove it

```bash
python3 tools/sync_native.py && python3 tools/check_drift.py
tools/odoo_install_test.sh 20
tools/test_matrix.sh   # all rows PASS, including the new ones
```

## 7. Engine floor policy

When the oldest supported version is dropped (e.g. v11 retires), raise the floor in
`engine/native/COMPAT.md`, remove the retired combos from `tools/engine_matrix.sh`,
and only then start using newer syntax in the engine.

## 8. Worked examples from this repo

- **Within a family** (v18 → v19): `diff -r -x __pycache__ -x native
  v18/pentaho_reports v19/pentaho_reports` — the differences are the route type
  (`json` → `jsonrpc`), manifest version, migrations folder name, README line, and
  the tests' `group_ids` awareness. That is the expected size of a same-family bump.
- **Across families** (v14 → v15): the JS swaps `action_manager.js`
  (`odoo.define` + `ActionManager.include`) for `action_service.js` (`@odoo-module` +
  registry), assets move from `views/assets.xml` into the manifest, and the dispatch
  alias keeps the v14 shape until v16 changes the signature. Run the same `diff -r`
  to see the full jump before attempting a new family.
