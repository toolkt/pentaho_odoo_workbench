# Task 11 report: v11

## Summary

Copied `v12/pentaho_reports` to `v11/` per the brief's Step 1 script, applied the Step 2
model edit (`@api.model_create_multi` → `@api.model` single-record `create`, explicit
`super(IrActionsReport, self)` calls), and the Step 3 JS edits (`require('report.report')`
in place of `require('web.ReportActionManager')`, `_executeReportAction` → `ir_actions_report`,
`doAction` → `do_action`, header comment reworded to Odoo 11). `python -m compileall` with
Odoo 11's venv, `sync_native.py`, and `check_drift.py` all clean.

The harness (`tools/odoo_install_test.sh 11`) initially reported 0 pentaho_reports test lines
even though the module installed successfully — the brief's assumption that Odoo 11's tagged()
no-op fallback would still let tests "run at install" was wrong for our harness's
`--without-demo=all` flag, and after fixing that, a second, independent Odoo-11-only bug
appeared in `HttpCase.authenticate()`'s cross-cursor visibility. Both are genuine Odoo 11 core
quirks, root-caused with file:line evidence against the read-only
`/Volumes/Workspace/Development/OdooWorkbench/odoo11/odoo` checkout, and fixed with the
smallest changes I could find, confined to `v11/pentaho_reports/tests/*.py`'s `tagged()`
fallback and `_make_user()` helper — no Odoo core files, no shared harness script, and no test
assertions/design were touched. See "Odoo-11-specific adaptations" below for full detail.

Final harness run: **`RESULT v11 PASS`**, 15/15 tests (`TestPentahoControllers` 8,
`TestPentahoRender` 7), both classes confirmed running in the log. `node --check` clean.
Committed as `bb746a8`.

## Step 1: copy + mechanical edits

Ran the brief's script verbatim.

```
$ grep "'version'" v11/pentaho_reports/__manifest__.py
    'version': '11.0.2.0.0',
$ ls v11/pentaho_reports/migrations/
11.0.2.0.0
```

README diff vs v12 (exactly the expected substitutions — title, "Odoo **11** build", the
Python-floor sentence, `/v11`; the "sibling folders `../v11` … `../v19`" sentence is unchanged
because it's the same fixed range used verbatim in every version's README, confirmed by
checking v13/v14/v15's copies before editing):

```
$ diff v12/pentaho_reports/README.md v11/pentaho_reports/README.md
1c1
< # pentaho_reports — Odoo 12
---
> # pentaho_reports — Odoo 11
4,5c4,5
< This folder is the Odoo **12** build; ... Odoo 12 itself allows 3.5 ...
---
> This folder is the Odoo **11** build; ... Odoo 11 itself allows 3.5 ...
7c7
< Install: copy this folder into your addons path (or `--addons-path=/path/to/v12`), then
---
> Install: copy this folder into your addons path (or `--addons-path=/path/to/v11`), then
11c11
< Note: Odoo 12 itself needs Pillow < 10 ...
---
> Note: Odoo 11 itself needs Pillow < 10 ...
```

## Step 2: model — Odoo 11 `create`

`v11/pentaho_reports/models/ir_actions_report.py`: replaced the multi-record
`@api.model_create_multi def create(self, vals_list): ...` with the brief's exact
single-record `@api.model def create(self, vals): ...`, and made the `write` override's
`super()` call explicit (`super(IrActionsReport, self).write(vals)`), matching the brief
verbatim. Checked the whole v11 folder for any `.create([...])` list-style calls that would
break under single-record `create` — none found; both test files already call
`self.env['res.users'].create(vals)` / `self.Report.create({...})` with a plain dict.

## Step 3: JS — Odoo 11 hooks

Confirmed against Odoo 11 core (`odoo/addons/web/static/src/js/report/qwebactionmanager.js`,
which `odoo.define`s as `'report.report'`) before editing:
- `ActionManager.include({ ir_actions_report: function (action, options) {...} })` is exactly
  the hook name Odoo 11's `web.ActionManager` dispatches report actions through (confirmed
  `odoo.define('web.ActionManager', ...)` at `odoo/addons/web/static/src/js/chrome/
  action_manager.js:1`, `do_action:` method at line 632).
- Applied the brief's edits verbatim: `require('report.report');  // core qweb handling; our
  include must layer on top of it`, `_executeReportAction` → `ir_actions_report`,
  `self.doAction(...)` → `self.do_action(...)`, header comment → "Odoo 11".

`depends: ['base', 'web']` in the manifest already covers `report.report` (it's defined inside
the `web` addon, not a separate `report` addon, on Odoo 11) — no manifest depends change
needed.

```
$ diff v12/pentaho_reports/static/src/js/action_manager.js v11/pentaho_reports/static/src/js/action_manager.js
5c5
<  * Pentaho report actions on the legacy web client (Odoo 12).
---
>  * Pentaho report actions on the legacy web client (Odoo 11).
18c18
< require('web.ReportActionManager');
---
> require('report.report');  // core qweb handling; our include must layer on top of it
110c110
<     _executeReportAction: function (action, options) {
---
>     ir_actions_report: function (action, options) {
165c165
<                 return self.doAction({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));
---
>                 return self.do_action({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));
```

`node --check v11/pentaho_reports/static/src/js/action_manager.js` → clean, both before and
after the final test-file fixes (JS untouched throughout).

## Step 4: compileall, sync, drift, harness

```
$ /Volumes/Workspace/Development/OdooWorkbench/odoo11/venv/bin/python -m compileall -q v11/pentaho_reports && echo V11_COMPILE_OK
V11_COMPILE_OK
$ python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py
OK: all native copies identical to engine/native
```

### First harness run — 0 pentaho_reports tests executed (root-caused, fixed)

`tools/odoo_install_test.sh 11` initially reported `exit=0, test lines=0` — module installed
without error, but neither `TestPentahoRender` nor `TestPentahoControllers` ran at all (only
`base`/`web`/`web_editor`'s own tests showed up in the log). The brief's Step 4 instruction to
"confirm ... TestPentahoRender/TestPentahoControllers ran" caught this immediately.

**Root cause** (confirmed by reading Odoo 11 source, not guessed): Odoo 11 has two,
mutually-exclusive test-running paths, neither of which is the "-test-tags" mechanism the
brief describes for 12+:
1. An at-install path inside `load_module_graph` (`odoo/modules/loading.py:205-210`), gated
   by `if has_demo:` — and `has_demo` is only true when demo data was actually loaded, which
   `--without-demo=all` (our harness, every version) forces to `{}` at
   `odoo/tools/config.py:472-474`. This path never fires under our harness.
2. A post-install path in `preload_registries` (`odoo/service/server.py:1066-1076`):
   `module_names = registry.updated_modules; ... run_unit_tests(module_name, dbname,
   position=runs_post_install)`. `runs_post_install` (`odoo/modules/module.py:486-492`)
   defaults to `False` unless the test class has a `post_install = True` class attribute set
   — which is exactly what `odoo.tests.tagged('post_install', ...)` does on Odoo 12+, but our
   fallback shim (`def tagged(*tags): return lambda cls: cls`) was a true no-op, so
   `post_install` was never set. Combined with (1) never firing, **no path ever ran our
   tests** under this harness's flags.

**Fix** (`v11/pentaho_reports/tests/test_render.py` and `tests/test_controllers.py`, both
tagged `@tagged('post_install', '-at_install')`): replaced the no-op fallback with a decorator
that sets the two class attributes Odoo 11's own `runs_at()` mechanism reads directly:

```python
except ImportError:  # Odoo 11: no odoo.tests.tagged, but the test runner itself already
    # reads post_install/at_install class attributes directly (module.py:478-492); set the
    # two attributes our tags map to.
    def tagged(*tags):
        def decorator(cls):
            if 'post_install' in tags:
                cls.post_install = True
            if '-at_install' in tags:
                cls.at_install = False
            return cls
        return decorator
```

This is not a workaround bolted onto our tests — it reimplements the exact mechanism Odoo 11
itself already exposes for this purpose (`runs_at_install = functools.partial(runs_at,
hook='at_install', default=True)`, `runs_post_install = functools.partial(runs_at,
hook='post_install', default=False)` — `module.py:491-492`), just without the `tagged()`
sugar that only exists from Odoo 12 onward. Confined to the two test files' compat shim; no
change to any assertion, fixture, or test design.

### Second issue — `HttpCase.authenticate()` cross-cursor visibility (root-caused, fixed)

After the tag fix, both test classes ran, but `TestPentahoControllers` had 3 errors, all in
the tests that create a non-admin user then call `self.authenticate(...)`
(`test_preview_allows_report_author_without_admin`,
`test_preview_rejects_internal_user_without_technical_access`,
`test_preview_rejects_portal_user`).

**Root cause**: `HttpCase.setUp()` (`odoo/tests/common.py:262-273`) calls
`super().setUp()` (`TransactionCase.setUp`, which opens `self.cr = self.registry.cursor()` —
at this point `registry.test_cr is None`, so this is a **plain, separate** `Cursor`/DB
connection) *before* calling `self.registry.enter_test_mode()`, which only then creates the
shared `registry.test_cr` (`odoo/modules/registry.py:459-486`) that every *subsequent*
`registry.cursor()` call returns instead (used by the werkzeug HTTP server thread and by
`res.users._login()`'s `with cls.pool.cursor() as cr:`, `odoo/addons/base/res/
res_users.py:468`). `TestCursor`'s "commit" (`sql_db.py:457-460`) only moves an internal
SAVEPOINT — it is never a real Postgres `COMMIT`, so nothing written through one of these two
cursors is ever visible to the other; they are permanently separate transactions until the
whole test tears down.

Worse, `HttpCase.authenticate()` itself (`common.py:283-301`) straddles both cursors in the
same method: `_login()` (called through `self.registry['res.users'].authenticate(...)`) reads
via the shared `test_cr`, but the very next line, `env = api.Environment(self.cr, uid, {})`
then `env['res.users'].context_get()`, reads back via `self.cr` — the original, separate
cursor. I confirmed this three-way split by hand across three iterations of the fix:
- user created via `self.env` (`self.cr`) only → `_login()`'s search (on `test_cr`) finds no
  match → "Login failed", `context_get()` then 500s with `IndexError: list index out of
  range` (`user.read([...])[0]` on an empty result).
- user created via `self.registry.cursor()` (`test_cr`) only, even with the returned
  recordset also rebound to a `test_cr`-backed env → `_login()` now succeeds (uid found), but
  `context_get()`'s read via `self.cr` then raises `odoo.exceptions.MissingError: Record does
  not exist or has been deleted` — `self.cr` genuinely cannot see a row that only exists in
  `test_cr`'s un-committed virtual transaction, no matter which cursor built the returned
  Python recordset.

The official Odoo 11 core test suite has exactly this same-idea idiom (`addons/point_of_sale/
tests/test_frontend.py:12-14`: `cr = self.registry.cursor(); assert cr ==
self.registry.test_cr`), but that pattern only helps when *every* access in the test method
stays on that one cursor — it does not help `HttpCase.authenticate()` itself, which is Odoo 11
framework code I cannot edit, and which unconditionally reads back through `self.cr` after
calling `_login()`.

**Fix** (`_make_user` in `test_controllers.py`): create the user via the normal `self.env`
(so it lands on `self.cr`, satisfying `context_get()`'s read), then `self.cr.commit()` — a
**real** Postgres commit on `self.cr` (it is a plain `Cursor`, not a `TestCursor`, so
`.commit()` is the genuine SQL `COMMIT`, unlike `test_cr`'s savepoint-shuffle). Under
READ COMMITTED, a real commit makes the row visible to every other session's next statement,
including `test_cr`'s subsequent `_login()` query. This satisfies both cursors
`authenticate()` touches, without patching Odoo core. It is safe here because `_make_user`
only ever runs against the throwaway `pentaho_test_v11` database, which
`tools/odoo_install_test.sh`'s `trap cleanup EXIT` drops unconditionally at the end of the
run — the real commit never needs to be (and isn't) rolled back by anything.

```python
user = self.env['res.users'].create(vals)
self.cr.commit()
return user
```

(Full in-file comment cites all four evidence points: `common.py:284-301`,
`res_users.py:468`, `registry.py:476-486`, and the confirmed-by-hand failure modes of the two
cursor-only-one-side attempts.)

### Final harness run

```
$ tools/odoo_install_test.sh 11
--- v11: exit=0, test lines=26
RESULT v11 PASS
```

Log evidence both test classes ran (grep from `odoo_v11.log`):
```
odoo.modules.module: odoo.addons.pentaho_reports.tests.test_controllers running tests.
odoo.addons.pentaho_reports.tests.test_controllers: Ran 8 tests in 1.157s
odoo.addons.pentaho_reports.tests.test_controllers: OK
odoo.modules.module: odoo.addons.pentaho_reports.tests.test_render running tests.
odoo.addons.pentaho_reports.tests.test_render: Ran 7 tests in 0.056s
odoo.addons.pentaho_reports.tests.test_render: OK
```
`grep -c "pentaho_reports.tests" .../odoo_v11.log` → 22 (> 0, per the brief's check).
8 + 7 = 15 tests, matching every other version.

No stray `pentaho_test_*` databases remained after the run (`psql -l | grep pentaho_test` →
empty); the harness's `trap cleanup EXIT` dropped `pentaho_test_v11` as expected.

## Files changed

- `v11/pentaho_reports/__manifest__.py` — version bump only
- `v11/pentaho_reports/migrations/11.0.2.0.0/` — renamed from `12.0.2.0.0`
- `v11/pentaho_reports/README.md` — version substitutions
- `v11/pentaho_reports/models/ir_actions_report.py` — single-record `create`, explicit `super()`
- `v11/pentaho_reports/static/src/js/action_manager.js` — `report.report` require,
  `ir_actions_report` hook, `do_action`, header comment
- `v11/pentaho_reports/tests/test_render.py` — Odoo-11-specific `tagged()` fallback (see above)
- `v11/pentaho_reports/tests/test_controllers.py` — same `tagged()` fallback, plus
  `_make_user()`'s `self.cr.commit()` fix (see above)
- everything else under `v11/pentaho_reports/` is an untouched copy of `v12/pentaho_reports`
  (native/, controllers/, views/, fixtures/, security, etc.)

## Self-review

`diff -r -x __pycache__ v12/pentaho_reports v11/pentaho_reports` shows exactly:
manifest version, migrations folder rename, README substitutions, model `create`/`write`,
JS (require line, hook name, `do_action`, header comment) — **plus** the two test files'
`tagged()` fallback and `_make_user()` fix described above, which the brief's checklist did
not anticipate. I'm calling this out explicitly rather than silently matching the checklist:
the brief's assumption ("Odoo 11: no test tags, tests run at install") does not hold under
this harness's `--without-demo=all` flag, and `HttpCase.authenticate()`'s cursor-splitting is
a genuine, independently-confirmed Odoo 11 core quirk — both are root-caused with file:line
evidence, fixed with the smallest change I could find, confined to the two test files, and
verified passing. No Odoo core file, no shared harness script (`tools/odoo_install_test.sh`),
and no test assertion/fixture/design was touched.

- Drift check: clean (`OK: all native copies identical to engine/native`)
- Compileall: `V11_COMPILE_OK` (Odoo 11's own venv, Python 3.6.8)
- `node --check`: clean
- No leftover `pentaho_test_*` databases
- Harness: `RESULT v11 PASS`, 15/15 tests, both test classes confirmed running

## Concerns

- The self-review checklist in the brief expected the diff to be limited to manifest/
  migrations/README/model/JS; it does not cover tests/*.py. I believe the two test-file
  changes are correctly in scope per the brief's own "Odoo 11 is the oldest target, so
  surprises are possible ... find the correct 11 form ... apply the smallest correct change,
  and document it with file:line evidence" clause, and I've documented both with full
  evidence above and in the source comments. Flagging for visibility rather than silently
  reporting DONE.
- `_make_user`'s `self.cr.commit()` performs a real, non-rolled-back Postgres commit mid-test.
  This is safe only because the target database (`pentaho_test_v11`) is unconditionally
  dropped after the harness run; it would not be an appropriate pattern against a persistent
  database.
