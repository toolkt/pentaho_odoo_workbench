# Task 10 report: v13 and v12

## Summary

Copied `v14/pentaho_reports` to `v13/` and `v12/` per the brief's Step 1 script, applied the
Step 2 model edits (drop `ondelete`, rename `_render_pentaho` → `render_pentaho`) to both, and
replaced v12's JS with the brief's jQuery-1.11-Deferred version plus the three amendment fixes
(`errorMessage` helper, two-arg `(error, event)` fail handler with `event.preventDefault()`,
reworded header comment). v13 keeps v14's already-fixed JS unchanged. Ran `sync_native.py` +
`check_drift.py` (clean) and both harnesses — v13 and v12 both PASS 15/15. Committed `b339cbf`.

One environment blocker was found and worked around (see "v12 environment issue" below):
the local `odoo12` venv has Pillow 11.3.0 installed against Odoo 12 core's requirements.txt pin
of `Pillow==6.1.0`; Odoo-12-core (not our module) calls the now-removed `PIL.Image.ANTIALIAS`
while loading `base`'s own `res_partner_data.xml`, which crashed *every* module install on that
venv, including a bare `-i base`. Fixed via a `PYTHONPATH`-injected `sitecustomize.py` shim
(`Image.ANTIALIAS = Image.LANCZOS` when absent) — no `pip install`, no venv edit, no repo file
touched; scoped to the one test invocation.

## Step 1: copy + mechanical edits

Ran the brief's loop verbatim for `N in 13 12`, plus the v12-only README floor sentence.

Verified:
```
$ grep "'version'" v13/pentaho_reports/__manifest__.py
    'version': '13.0.2.0.0',
$ grep "'version'" v12/pentaho_reports/__manifest__.py
    'version': '12.0.2.0.0',
$ ls v13/pentaho_reports/migrations/
13.0.2.0.0
$ ls v12/pentaho_reports/migrations/
12.0.2.0.0
```
v13 README: `# pentaho_reports — Odoo 13`, `Odoo **13** build`, `Odoo 13's own floor`, `/v13`.
v12 README: `# pentaho_reports — Odoo 12`, `Odoo **12** build`,
`Python ≥ 3.6 (this build's floor; Odoo 12 itself allows 3.5, which the shared renderer does
not support)`, `/v12`.

## Step 2: model edits (both)

`models/ir_actions_report.py` in v13 and v12 (identical edits, applied separately):
- `report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho Report')])` — dropped
  the `ondelete={'pentaho': 'set default'}` kwarg (ignored/unsupported before 14).
- `_render_pentaho(self, res_ids, data=None)` → `render_pentaho(self, res_ids, data=None)`
  (no underscore — Odoo 11–13's `render()` looks up `render_<type>`), docstring reworded to
  "Odoo 11-13 generic dispatch: ir.actions.report.render(res_ids, data) calls
  render_<report_type>(res_ids, data) on the report record."

`diff v13/.../ir_actions_report.py v12/.../ir_actions_report.py` → identical (exit 0), as expected.

## Step 3: v12 JS (brief content + amendment)

Wrote `v12/pentaho_reports/static/src/js/action_manager.js` from the brief's file verbatim, with
the three amendment changes applied:

1. Added the `errorMessage(error)` helper next to `getBrowserInfo`, copied verbatim from the
   amendment (normalizes the three error shapes: own `Error`, `_rpc` rejection, `session.get_file`
   parsed exception).
2. Replaced the final fail handler of `_executePentahoReportAction`'s `.then()` chain with the
   two-argument `(error, event)` form: calls `event.preventDefault()` when `event` carries one
   (so `ajax.js` doesn't also pop the core crash dialog), calls `self.do_warn(...,
   errorMessage(error), true)`, and re-rejects.
3. Reworded the header comment's `session.get_file` sentence to: "(session.get_file POSTs a
   form with token + csrf_token and polls for the fileToken cookie the route sets; its complete
   callback unblocks the UI)".

v13's JS was left untouched (copied from v14 in Step 1, no further edits) — confirmed identical:
```
$ diff v14/pentaho_reports/static/src/js/action_manager.js v13/pentaho_reports/static/src/js/action_manager.js
(no output, exit 0)
```

## Step 4: sync, drift, both harnesses

```
$ python3 tools/sync_native.py
synced v12/pentaho_reports/native
synced v13/pentaho_reports/native
synced v14/pentaho_reports/native
... (v15-v19 also synced)

$ python3 tools/check_drift.py
OK: all native copies identical to engine/native
```

### v13
```
$ tools/odoo_install_test.sh 13
--- v13: exit=0, test lines=21
RESULT v13 PASS
```
Log (`odoo_v13.log`): `Ran 8 tests in 0.294s` (test_controllers) + `Ran 7 tests in 0.076s`
(test_render) = 15/15, `All post-tested in 0.40s, 362 queries`, 0 ERROR/CRITICAL/Traceback lines.

### v12 — environment issue found, worked around, then PASS

First run (no workaround) failed **before pentaho_reports was ever loaded**:
```
$ tools/odoo_install_test.sh 12
--- v12: exit=255, test lines=0
2026-08-21 09:36:36,991 43742 ERROR pentaho_test_v12 odoo.sql_db: bad query:
  UPDATE ir_module_module SET state='installed' WHERE state IN ('to remove', 'to upgrade')
ERROR: relation "ir_module_module" does not exist
...
  File ".../odoo/tools/image.py", line 124, in image_resize_and_sharpen
    image.thumbnail(size, Image.ANTIALIAS)
AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'
...
odoo.tools.convert.ParseError: "module 'PIL.Image' has no attribute 'ANTIALIAS'" while parsing
  .../odoo/addons/base/data/res_partner_data.xml:4, near
<record id="main_partner" model="res.partner" ...>
RESULT v12 FAIL
```

Root cause, confirmed by inspection (not our module — this happens during `base`'s own bootstrap
data load, `init db`, on a brand-new throwaway DB, before `-i pentaho_reports` gets a chance to
run):
```
$ /Volumes/Workspace/Development/OdooWorkbench/odoo12/venv/bin/python -c "import PIL; print(PIL.__version__)"
11.3.0
$ grep -i pillow /Volumes/Workspace/Development/OdooWorkbench/odoo12/odoo/requirements.txt
Pillow==4.0.0 ; python_version < '3.7'
Pillow==6.1.0 ; python_version >= '3.7'
$ grep -n "Image.ANTIALIAS" /Volumes/Workspace/Development/OdooWorkbench/odoo12/odoo/odoo/tools/image.py
124:            image.thumbnail(size, Image.ANTIALIAS)
232:            thumbnail.thumbnail(size, Image.ANTIALIAS)
```
The `odoo12` venv has Pillow 11.3.0 installed, but Odoo 12 core's `requirements.txt` pins
`Pillow==6.1.0`; the two are out of sync in this local environment (pre-existing, unrelated to
this task — a venv provisioning drift). Pillow removed the deprecated `Image.ANTIALIAS` alias
(for `Image.LANCZOS`) in 10.0; Odoo 12 core's `odoo/tools/image.py` still calls it while resizing
the demo-company logo in `base/data/res_partner_data.xml`, which loads unconditionally on every
fresh DB regardless of `--without-demo` or which addon is being installed. Confirmed unrelated to
our module: v13 core code already uses `Image.LANCZOS` (compatible), so v13 never hit this.

Constraints forbid `pip install` into any Odoo venv and hand-editing vendor code, so instead of
altering the venv or Odoo core, applied a `PYTHONPATH`-injected `sitecustomize.py` shim, scoped
to this one test invocation only (no venv file touched, no repo file touched):
```python
# scratchpad/pil_compat_shim/sitecustomize.py
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS') and hasattr(Image, 'LANCZOS'):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    pass
```
```
$ PYTHONPATH=.../scratchpad/pil_compat_shim /Volumes/Workspace/Development/OdooWorkbench/odoo12/venv/bin/python \
    -c "from PIL import Image; print('ANTIALIAS present:', hasattr(Image, 'ANTIALIAS'))"
ANTIALIAS present: True

$ PYTHONPATH=.../scratchpad/pil_compat_shim tools/odoo_install_test.sh 12
--- v12: exit=0, test lines=26
RESULT v12 PASS
```
Log (`odoo_v12.log`): `Ran 8 tests in 0.753s` (test_controllers) + `Ran 7 tests in 0.052s`
(test_render) = 15/15, both `OK`, `All post-tested in 0.91s, 439 queries`, 0
ERROR/CRITICAL/Traceback lines. `test_core_render_dispatch_finds_pentaho` ran and passed,
confirming the `render_pentaho` hook is reached by Odoo 12's generic `render()` dispatch.

## `node --check` and `errorMessage` sanity check

```
$ node --check v13/pentaho_reports/static/src/js/action_manager.js && echo "v13 NODE_CHECK_OK"
v13 NODE_CHECK_OK
$ node --check v12/pentaho_reports/static/src/js/action_manager.js && echo "v12 NODE_CHECK_OK"
v12 NODE_CHECK_OK

$ node scratchpad/check_errorMessage.js v12/pentaho_reports/static/src/js/action_manager.js
PASS: own Error -> "x"
PASS: _rpc rejection (message is odoo error object) -> "real text"
PASS: session.get_file parsed exception -> "srv"
PASS: undefined -> "Unknown error"
```
(same checker script used for v14 in task-9; reused unmodified against the v12 file — exit 0,
all 4 pass)

## Self-review

```
$ diff -r -x __pycache__ v14/pentaho_reports v13/pentaho_reports
```
Shows only: `README.md` (Odoo 14→13 text substitutions), `__manifest__.py` (version string),
`migrations/14.0.2.0.0` vs `migrations/13.0.2.0.0` (folder rename), `models/ir_actions_report.py`
(dropped `ondelete`, renamed `_render_pentaho`→`render_pentaho` + docstring). Nothing else.

```
$ diff -r -x __pycache__ v13/pentaho_reports v12/pentaho_reports
```
Shows the same four categories (README, manifest version, migrations folder, model) plus
`static/src/js/action_manager.js` (full jQuery-Deferred rewrite) — exactly the expected set,
nothing extra.

Both diffs match the task's stated self-review criteria exactly.

`python3 tools/check_drift.py` → `OK: all native copies identical to engine/native`.

No leftover `pentaho_test_*` databases (`psql -l | grep pentaho` → empty after both runs; the
harness's `trap cleanup EXIT` dropped each throwaway DB).

`git status --short` after commit → clean (only `v12/` and `v13/` were added, no other repo
files touched — the PIL shim lives entirely in the scratchpad directory, never staged).

## Files changed

- `v13/pentaho_reports/**` (new, 39 files) — copy of v14 + `__manifest__.py` version,
  `migrations/13.0.2.0.0/`, `README.md`, `models/ir_actions_report.py` edits.
- `v12/pentaho_reports/**` (new, 39 files) — copy of v14 + `__manifest__.py` version,
  `migrations/12.0.2.0.0/`, `README.md`, `models/ir_actions_report.py` edits,
  `static/src/js/action_manager.js` full rewrite.

## Commit

```
b339cbf v12, v13: render_pentaho dispatch, no selection ondelete, v12 do_notify/do_warn
```
78 files changed, 9809 insertions(+).

## Concerns

- **Local `odoo12` venv environment drift** (not a defect in this task's deliverable): Pillow
  11.3.0 is installed against Odoo 12 core's `Pillow==6.1.0` pin, which breaks `base` module
  bootstrap on *any* fresh DB via the now-removed `Image.ANTIALIAS`. Worked around for this run
  with a `PYTHONPATH` `sitecustomize.py` shim (`Image.ANTIALIAS = Image.LANCZOS`), applied
  outside the repo and outside the venv, scoped to the one invocation — no `pip install`, no
  venv/vendor file edited, no repo file touched. This is a standing local-environment issue,
  independent of `pentaho_reports`, that will resurface for any future `tools/odoo_install_test.sh
  12` run (or any other module install against this venv) unless the venv's Pillow is pinned to
  match Odoo 12's own `requirements.txt`, or the harness is updated to set `PYTHONPATH` at that
  shim permanently. Flagging for whoever owns the `OdooWorkbench` venvs; happy to make that
  permanent fix (or move the shim into `tools/`) if instructed — did not do so here since it
  wasn't in this task's file list and touches shared infra outside this repo's stated scope.
- No other concerns. Model and JS edits match the brief and amendment exactly; both harnesses
  pass 15/15 with 0 errors; self-review diffs match the prescribed shape exactly; drift clean;
  no leftover databases.

## Fix round 1: bake the PIL shim into the repo harness (coordinator ruling)

The coordinator flagged that `tools/odoo_install_test.sh 12` as delivered could not
reproduce `RESULT v12 PASS` without the out-of-repo scratchpad `PYTHONPATH` hack, and that
a later acceptance run (`tools/test_matrix.sh`) calls the harness directly with no such
hack available. Ruling: move the shim into the repo's harness itself, venv untouched.

### What changed

1. **New file `tools/pil_compat/sitecustomize.py`** — written verbatim from the coordinator's
   spec: restores `PIL.Image.ANTIALIAS = PIL.Image.LANCZOS` only when `ANTIALIAS` is missing
   and `LANCZOS` is present (no-op on Pillow < 10, no-op on any other name).

2. **`tools/odoo_install_test.sh`** — added right after the `MEM_FLAG` block:
   ```bash
   # Odoo <= 12 still calls PIL.Image.ANTIALIAS (removed in Pillow 10); newer local venvs would
   # fail to bootstrap `base`. tools/pil_compat/sitecustomize.py restores the alias when absent.
   PIL_SHIM=""
   if [ "$N" -le 12 ]; then PIL_SHIM="$REPO/tools/pil_compat"; fi
   ```
   and prefixed the odoo-bin invocation:
   ```bash
   ( cd "$WB/odoo" && PYTHONPATH="${PIL_SHIM}${PYTHONPATH:+:$PYTHONPATH}" "$PY" "$ODOO_BIN" \
   ```
   `bash -n tools/odoo_install_test.sh` → syntax OK. Verified `${PYTHONPATH:+:$PYTHONPATH}` is
   `set -u`-safe when `PYTHONPATH` is completely unset:
   ```
   $ bash -uc 'unset PYTHONPATH; echo "[${PYTHONPATH:+:$PYTHONPATH}]"'
   []
   ```
   For N=13 (and all N>12), `PIL_SHIM=""` and `PYTHONPATH` resolves to whatever the caller's
   env already had (empty here) — no behavior change for v13-v19.

3. **`v12/pentaho_reports/README.md`** — added the one-line note after the install paragraph:
   `Note: Odoo 12 itself needs Pillow < 10 (it uses the removed Image.ANTIALIAS); this module
   has no such requirement.`

### Re-run, no external PYTHONPATH

Confirmed the shell had no `PYTHONPATH` set before either run:
```
$ echo "PYTHONPATH=[${PYTHONPATH:-unset}]"
PYTHONPATH=[unset]
```

```
$ tools/odoo_install_test.sh 12
--- v12: exit=0, test lines=26
RESULT v12 PASS
```
Log (`odoo_v12.log`): `Ran 8 tests in 0.725s` (test_controllers) + `Ran 7 tests in 0.045s`
(test_render) = 15/15, `All post-tested in 0.80s, 436 queries`, 0 ERROR/CRITICAL/Traceback
lines. No `PYTHONPATH` set in the invoking shell — the shim is now applied entirely by the
harness itself for N=12.

```
$ tools/odoo_install_test.sh 13
--- v13: exit=0, test lines=21
RESULT v13 PASS
```
Log (`odoo_v13.log`): `Ran 8 tests in 0.299s` + `Ran 7 tests in 0.056s` = 15/15,
`All post-tested in 0.39s, 362 queries`, 0 ERROR/CRITICAL/Traceback lines — no regression;
v13 gets `PIL_SHIM=""` (N=13 > 12) and behaves exactly as before.

Deleted the old scratchpad shim directory (`scratchpad/pil_compat_shim/`) — confirmed gone.
No leftover `pentaho_test_*` databases after either run (`psql -l | grep pentaho` empty).

### Commit

```
a932e6d tools: bake the Odoo<=12 PIL.ANTIALIAS compat shim into odoo_install_test.sh
```
3 files changed (`tools/odoo_install_test.sh`, `tools/pil_compat/sitecustomize.py` new,
`v12/pentaho_reports/README.md`), 21 insertions(+), 1 deletion(-).

### Updated concerns

The standing local-environment concern from the first pass is now resolved: the shim lives in
the repo, is applied automatically by `tools/odoo_install_test.sh` for N<=12 (so
`tools/test_matrix.sh` will pick it up with no extra steps), the venv itself remains untouched
(no `pip install`), and v13-v19 are unaffected (`PIL_SHIM` empty for N>12). No open concerns
remain from this round.
