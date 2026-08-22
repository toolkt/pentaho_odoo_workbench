# Task 8 report: v16 and v15 (family B: OWL registry + `attrs` views)

## Summary

Copied `v17/pentaho_reports` to `v16/` and `v15/`, applied the version-specific edits from
the brief (attrs-domain views for both, `env._t` for both, v15 recordset dispatch hook),
synced/drift-checked, and ran both Odoo harnesses to a clean PASS. One harness bug was
found and fixed along the way (root-caused, not a module issue — see Concerns/Fix below).

## Steps performed

### Step 1 — copy + mechanical edits
```bash
for N in 16 15; do
  rm -rf v$N && mkdir -p v$N && cp -R v17/pentaho_reports v$N/pentaho_reports
  find v$N -name __pycache__ -type d -prune -exec rm -rf {} +
  sed -i '' "s/'version': '17.0.2.0.0'/'version': '$N.0.2.0.0'/" v$N/pentaho_reports/__manifest__.py
  mv v$N/pentaho_reports/migrations/17.0.2.0.0 v$N/pentaho_reports/migrations/$N.0.2.0.0
  sed -i '' "s/Odoo 17/Odoo $N/g; s/\*\*17\*\*/**$N**/; s/Python ≥ 3.10 (Odoo $N's own floor)/Python ≥ 3.7 (Odoo $N's own floor)/; s/\/v17/\/v$N/" v$N/pentaho_reports/README.md
done
```
All `sed -i ''` substitutions matched cleanly on the first try — verified with grep afterward
(manifest `version` fields, migrations folder rename, and every README line the brief's
sed touched). No hand-editing needed for Step 1.

### Step 2 — `views/report_views.xml` → `attrs` domains
Replaced the whole file in both `v16/pentaho_reports/views/report_views.xml` and
`v15/pentaho_reports/views/report_views.xml` with the brief's XML verbatim. Confirmed
`diff v16/.../report_views.xml v15/.../report_views.xml` — byte-identical.

### Step 3 — JS `_t` (both versions)
In `static/src/js/action_service.js` (both v16 and v15):
- Removed `import { _t } from "@web/core/l10n/translation";`
- Added `const _t = env._t;` as the first statement inside `pentahoReportHandler`, right
  after `if (action.report_type === "pentaho") {`.

Verified no leftover `@web/core/l10n/translation` references in either tree, and the
`const _t = env._t;` line lands correctly inside the handler in both files.

### Step 4 — v15-only dispatch hook
Replaced `v15/pentaho_reports/models/ir_actions_report.py`'s `_render_pentaho` method
(previously the v16-style `@api.model _render_pentaho(self, report_ref, res_ids, data=None)`
copied from v17) with the brief's recordset form:
```python
    def _render_pentaho(self, res_ids, data=None):
        """Odoo 14/15 generic dispatch: ir.actions.report._render(res_ids, data)
        calls _render_<report_type>(res_ids, data) on the report record."""
        return self._render_pentaho_report(res_ids, data)
```
Confirmed v16 was left untouched — it still has the `@api.model` + `report_ref` form.

### Step 5 — sync, drift, both Odoo runs
```
python3 tools/sync_native.py       -> synced v15/v16/v17/v18/v19 (no changes needed)
python3 tools/check_drift.py       -> OK: all native copies identical to engine/native
```

First attempt at `tools/odoo_install_test.sh 15` **failed** — see Concerns/Fix below for
root cause and the harness patch. After the fix, both runs pass cleanly, and a full
re-run of v15–v19 confirms no regression to the already-shipped versions.

## Concern found and fixed: Odoo 15-on-macOS core bug in `set_limit_memory_hard`

`tools/odoo_install_test.sh 15` initially failed at server startup, before any addon
loading, with:
```
ValueError: current limit exceeds maximum limit
  File ".../odoo15/odoo/odoo/service/server.py", line 83, in set_limit_memory_hard
    resource.setrlimit(rlimit, (config['limit_memory_hard'], hard))
```
Root cause: Odoo 15's `service/server.py` calls `set_limit_memory_hard()` unconditionally
in `ThreadedServer.start()` on any POSIX system, and on Darwin tries
`resource.setrlimit(RLIMIT_RSS, ...)`, which macOS rejects with `EINVAL` (surfaced by
CPython as this `ValueError`). Odoo 16 fixed this upstream by guarding the call to
`platform.system() == 'Linux'` only (confirmed by diffing `odoo15/.../server.py` against
`odoo16/.../server.py`) — this is a genuine Odoo-15-core/macOS incompatibility, not
something wrong with the module or its views/tests.

Fix (glue/harness, not the module, not the test): in `tools/odoo_install_test.sh`, pass
`--limit-memory-hard=0` (a legitimate Odoo CLI flag; `0` is falsy so the buggy call
becomes a no-op) when running on Darwin for `N < 16`:
```bash
MEM_FLAG=()
if [ "$N" -lt 16 ] && [ "$(uname -s)" = "Darwin" ]; then MEM_FLAG=(--limit-memory-hard=0); fi
...
--http-port="$PORT" "${LP_FLAG[@]}" ${MEM_FLAG[@]+"${MEM_FLAG[@]}"} \
```
First cut of this used `"${MEM_FLAG[@]}"` unconditionally, which hit a second, unrelated
bug: macOS's default `/bin/bash` (3.2) throws "unbound variable" under `set -u` when
expanding an **empty** array with `"${arr[@]}"` — a long-fixed bash bug still present in
3.2. Matched the existing `${TEST_TAGS[@]+"${TEST_TAGS[@]}"}` idiom already used in this
same script for `TEST_TAGS`, and the fix held. (The most recent pre-existing commit on
this branch, "v19 fixup: portable empty-array guard in harness, accurate comments", shows
this exact class of bug has hit this script before — consistent precedent.)

After the fix: v16, v15, and (as a regression check) v17/v18/v19 all pass.

## `diff -r` outputs (self-review)

### v17 → v16 (excluding `__pycache__`)
```
diff -r --exclude=__pycache__ v17/pentaho_reports v16/pentaho_reports

diff --color -r --exclude=__pycache__ v17/pentaho_reports/README.md v16/pentaho_reports/README.md
1c1
< # pentaho_reports — Odoo 17
---
> # pentaho_reports — Odoo 16
4,5c4,5
< This folder is the Odoo **17** build; sibling folders `../v11` … `../v19` are the same module
< for other versions. Requires Python ≥ 3.10 (Odoo 17's own floor) and reportlab (bundled with Odoo).
---
> This folder is the Odoo **16** build; sibling folders `../v11` … `../v19` are the same module
> for other versions. Requires Python ≥ 3.7 (Odoo 16's own floor) and reportlab (bundled with Odoo).
7c7
< Install: copy this folder into your addons path (or `--addons-path=/path/to/v17`), then
---
> Install: copy this folder into your addons path (or `--addons-path=/path/to/v16`), then

diff --color -r --exclude=__pycache__ v17/pentaho_reports/__manifest__.py v16/pentaho_reports/__manifest__.py
4c4
<     'version': '17.0.2.0.0',
---
>     'version': '16.0.2.0.0',

Only in v16/pentaho_reports/migrations: 16.0.2.0.0
Only in v17/pentaho_reports/migrations: 17.0.2.0.0
(contents of post-migrate.py inside are byte-identical between the two folders)

diff --color -r --exclude=__pycache__ v17/pentaho_reports/static/src/js/action_service.js v16/pentaho_reports/static/src/js/action_service.js
5d4
< import { _t } from "@web/core/l10n/translation";
92a92
>         const _t = env._t;

diff --color -r --exclude=__pycache__ v17/pentaho_reports/views/report_views.xml v16/pentaho_reports/views/report_views.xml
10,14c10,13
<                 <field name="pentaho_report_output_type" 
<                        invisible="report_type != 'pentaho'" 
<                        required="report_type == 'pentaho'"/>
<                 <field name="pentaho_direct_print" 
<                        invisible="report_type != 'pentaho' or pentaho_report_output_type != 'pdf'"
---
>                 <field name="pentaho_report_output_type"
>                        attrs="{'invisible': [('report_type', '!=', 'pentaho')], 'required': [('report_type', '=', 'pentaho')]}"/>
>                 <field name="pentaho_direct_print"
>                        attrs="{'invisible': ['|', ('report_type', '!=', 'pentaho'), ('pentaho_report_output_type', '!=', 'pdf')]}"
16c15
<                 <field name="pentaho_file" 
---
>                 <field name="pentaho_file"
18,19c17
<                        invisible="report_type != 'pentaho'" 
<                        required="report_type == 'pentaho' and not pentaho_load_file"/>
---
>                        attrs="{'invisible': [('report_type', '!=', 'pentaho')], 'required': [('report_type', '=', 'pentaho'), ('pentaho_load_file', '=', False)]}"/>
21c19
<                 <field name="pentaho_load_file" invisible="report_type != 'pentaho'"/>
---
>                 <field name="pentaho_load_file" attrs="{'invisible': [('report_type', '!=', 'pentaho')]}"/>
23,25d20
<             
<             <!-- Don't hide the standard model field for Pentaho reports -->
<             <!-- The model field remains visible and usable as normal -->
28c23
<     
---
> 
36,37c31,32
<                 <filter string="Pentaho Reports" 
<                         name="pentaho_reports" 
---
>                 <filter string="Pentaho Reports"
>                         name="pentaho_reports"
42,43c37
< 
< </odoo>
\ No newline at end of file
---
> </odoo>
```
(The trailing whitespace / blank-line / final-newline diffs are inherent to pasting the
brief's XML verbatim over the v17 original, which had trailing spaces and no final
newline — not something introduced beyond the required content change.)

### v16 → v15 (excluding `__pycache__`)
```
diff -r --exclude=__pycache__ v16/pentaho_reports v15/pentaho_reports

diff --color -r --exclude=__pycache__ v16/pentaho_reports/README.md v15/pentaho_reports/README.md
1c1
< # pentaho_reports — Odoo 16
---
> # pentaho_reports — Odoo 15
4,5c4,5
< This folder is the Odoo **16** build; sibling folders `../v11` … `../v19` are the same module
< for other versions. Requires Python ≥ 3.7 (Odoo 16's own floor) and reportlab (bundled with Odoo).
---
> This folder is the Odoo **15** build; sibling folders `../v11` … `../v19` are the same module
> for other versions. Requires Python ≥ 3.7 (Odoo 15's own floor) and reportlab (bundled with Odoo).
7c7
< Install: copy this folder into your addons path (or `--addons-path=/path/to/v16`), then
---
> Install: copy this folder into your addons path (or `--addons-path=/path/to/v15`), then

diff --color -r --exclude=__pycache__ v16/pentaho_reports/__manifest__.py v15/pentaho_reports/__manifest__.py
4c4
<     'version': '16.0.2.0.0',
---
>     'version': '15.0.2.0.0',

Only in v15/pentaho_reports/migrations: 15.0.2.0.0
Only in v16/pentaho_reports/migrations: 16.0.2.0.0
(contents of post-migrate.py inside are byte-identical between the two folders)

diff --color -r --exclude=__pycache__ v16/pentaho_reports/models/ir_actions_report.py v15/pentaho_reports/models/ir_actions_report.py
162,167c162,165
<     @api.model
<     def _render_pentaho(self, report_ref, res_ids, data=None):
<         """Odoo >= 16 generic dispatch: ir.actions.report._render() calls
<         _render_<report_type>(report_ref, res_ids, data)."""
<         report = self._get_report(report_ref)
<         return report._render_pentaho_report(res_ids, data)
---
>     def _render_pentaho(self, res_ids, data=None):
>         """Odoo 14/15 generic dispatch: ir.actions.report._render(res_ids, data)
>         calls _render_<report_type>(res_ids, data) on the report record."""
>         return self._render_pentaho_report(res_ids, data)
```
`views/report_views.xml` and `static/src/js/action_service.js` are byte-identical between
v16 and v15 (both already carry the Step 2/3 edits applied to both versions).

Both diffs match the self-review criteria exactly: v17→v16 touches only manifest version,
migrations folder, README, views XML, and the JS `_t` lines; v16→v15 additionally touches
only the model's `_render_pentaho` hook.

## Harness runs — test summary lines

### v16
```
--- v16: exit=0, test lines=20
RESULT v16 PASS
```
From the log:
```
odoo.tests.stats: pentaho_reports: 19 tests 2.16s 436 queries
odoo.tests.result: 0 failed, 0 error(s) of 15 tests when loading database 'pentaho_test_v16'
```

### v15
```
--- v15: exit=0, test lines=19
RESULT v15 PASS
```
From the log:
```
odoo.service.server: 15 post-tests in 2.13s, 408 queries
odoo.tests.runner: 0 failed, 0 error(s) of 15 tests when loading database 'pentaho_test_v15'
```
`TestPentahoRender.test_core_render_dispatch_finds_pentaho` ran and passed on v15, exercising
the recordset-form `_render_pentaho(res_ids, data)` dispatch hook via `Report._render(self.partners.ids)`.

### Regression check (v17, v18, v19 — shared harness script was edited)
```
--- v17: exit=0, test lines=22
RESULT v17 PASS
--- v18: exit=0, test lines=28
RESULT v18 PASS
--- v19: exit=0, test lines=19
RESULT v19 PASS
```
No regression from the `tools/odoo_install_test.sh` fix (the `MEM_FLAG` branch is a no-op
for `N >= 16`).

## Files changed

- Created: `v16/pentaho_reports/**` (copied from v17, edited manifest/migrations/README/views/JS)
- Created: `v15/pentaho_reports/**` (copied from v16 lineage, edited manifest/migrations/README/views/JS, plus the model dispatch hook)
- Modified: `tools/odoo_install_test.sh` — added the `--limit-memory-hard=0` Darwin/`N<16`
  workaround for the Odoo-15-core macOS `RLIMIT_RSS` bug, using the same portable
  empty-array bash idiom already used for `TEST_TAGS` in this script.

## Self-review

- `diff -r v17/pentaho_reports v16/pentaho_reports` (excluding `__pycache__`, which is
  gitignored and not committed): only manifest version, migrations folder, README,
  views XML, JS `_t` lines. Confirmed above.
- `diff -r v16/pentaho_reports v15/pentaho_reports`: same set plus the model's
  `_render_pentaho` hook. Confirmed above.
- `python3 tools/check_drift.py` → `OK: all native copies identical to engine/native`.
- No leftover `pentaho_test_*` DBs (`psql -l` checked after both runs — cleanup trap in
  `odoo_install_test.sh` drops the DB unconditionally on exit).
- `git status --short` after commit is clean; only `v15/`, `v16/`, and
  `tools/odoo_install_test.sh` were staged and committed (no `native/` hand-edits, no
  stray files).
- `v16/pentaho_reports/models/ir_actions_report.py` still uses the `@api.model
  _render_pentaho(self, report_ref, res_ids, data=None)` form (untouched, as required —
  Step 4 is v15-only).

## Concerns

- The Odoo-15/macOS `set_limit_memory_hard` bug is upstream Odoo 15 core behavior, not
  something in this repo's control beyond working around it in the local test harness.
  The workaround (`--limit-memory-hard=0` on Darwin for `N < 16`) only disables an RSS
  memory-limit enforcement mechanism for the local throwaway test run; it has no bearing
  on production Odoo 15 deployments (which typically run on Linux, where the bug does not
  manifest, and where `--limit-memory-hard` still defaults to its normal value unless a
  deployer overrides it).
- No other concerns. Both `RESULT v16 PASS` and `RESULT v15 PASS` are clean, 0
  failed/0 error(s) of 15 tests each, matching v17/v18/v19's pattern exactly.
