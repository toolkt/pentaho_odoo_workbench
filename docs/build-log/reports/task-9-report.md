# Task 9 report: v14 — the legacy-web-client reference (family A)

Status: **DONE**

## What was done

Followed brief steps 1-8 verbatim, with one deviation in Step 1 (documented below,
purely a build-environment flag, no repo files touched).

### Step 1 — reportlab into the odoo14 venv

`pip install "reportlab==3.5.55"` initially **failed** building the `_renderPM` C
extension:

```
src/rl_addons/renderPM/gt1/gt1-namecontext.c:100:9: error: call to undeclared library
function 'strlen' with type 'unsigned long (const char *)'; ISO C99 and later do not
support implicit function declarations [-Wimplicit-function-declaration]
...
3 errors generated.
error: command '/usr/bin/clang' failed with exit code 1
ERROR: Failed building wheel for reportlab
```

Root cause: reportlab 3.5.55's bundled `gt1-namecontext.c` (vendored ~2015-era C,
part of the FreeType/libart renderer extension) calls `strlen`/`memcpy`/`strcmp`
without `#include <string.h>`. Modern Xcode/Clang on this Mac (macOS 26 SDK)
promotes implicit-function-declaration from warning to hard error by default,
which older C sources like this trip over. This is a compiler-toolchain issue,
not a repo issue — no source file was patched. Fix: pass a permissive CFLAGS for
just this one build:

```bash
CFLAGS="-Wno-error=implicit-function-declaration" \
  /Volumes/Workspace/Development/OdooWorkbench/odoo14/venv/bin/python -m pip install -q "reportlab==3.5.55"
```

This succeeded silently (no wheel-cache reuse — it did a real compile). Verified:

```
$ /Volumes/Workspace/Development/OdooWorkbench/odoo14/venv/bin/python -c "import reportlab; print(reportlab.Version)"
3.5.55
```

Matches the expected pin exactly. No other packages were installed or upgraded
in the odoo14 venv, and no other Odoo venv was touched.

### Step 2 — copy v15 → v14 + mechanical edits

Ran the brief's commands verbatim:
- `rm -rf v14 && mkdir -p v14 && cp -R v15/pentaho_reports v14/pentaho_reports`, pruned `__pycache__`
- `sed -i ''` version bump `15.0.2.0.0` → `14.0.2.0.0` in `__manifest__.py` — verified via grep, matched exactly
- `mv .../migrations/15.0.2.0.0 .../migrations/14.0.2.0.0` — verified, migration file content unchanged (`diff` empty)
- `sed -i ''` chain on `README.md` (4 patterns: `Odoo 15`→`Odoo 14` global, `**15**`→`**14**`,
  the Python-floor sentence, `/v15`→`/v14`) — all four applied correctly; read the
  resulting README and confirmed every "15" reference became "14" with no stray misses
  (the sed-ordering trick in pattern 3, matching the *already-substituted* "Odoo 14's own
  floor" text, worked as designed since sed applies expressions in sequence per line)
- `rm v14/pentaho_reports/static/src/js/action_service.js`

All sed patterns matched cleanly on the first try; no hand-editing was needed for this step.

### Step 3 — manifest: XML asset bundle instead of `assets` key

Used Edit (not sed, since this is a multi-line structural change) to replace:
```python
    'data': [
        'views/report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pentaho_reports/static/src/js/print_min.js',
            'pentaho_reports/static/src/js/action_service.js',
        ],
    },
```
with:
```python
    'data': [
        'views/assets.xml',
        'views/report_views.xml',
    ],
```
Verified via grep — the `assets` key is fully gone, `data` lists `views/assets.xml` before `views/report_views.xml`.

### Step 4 — `views/assets.xml`

Created verbatim from the brief (inherits `web.assets_backend`, xpath position="inside",
two `<script>` tags for `print_min.js` and `action_manager.js`).

### Step 5 — `static/src/js/action_manager.js`

Created verbatim from the brief — the full legacy `odoo.define('pentaho_reports.ActionManager', ...)`
module with the `ActionManager.include({ _executeReportAction, _executePentahoReportAction })`
pattern, `session.get_file` download path, Print.js/`printPDFInNewWindow` direct-print path,
and `guardedCatch` error handling. No text was altered from the brief.

### Step 6 — dispatch hook verification

```
$ grep -n "def _render_pentaho\|def render_pentaho" v14/pentaho_reports/models/ir_actions_report.py
131:    def _render_pentaho_report(self, res_ids, data=None):
162:    def _render_pentaho(self, res_ids, data=None):
```
`_render_pentaho(self, res_ids, data=None)` present — the recordset-hook form, correct for
Odoo 14 (copied unmodified from v15). `ondelete={'pentaho': 'set default'}` on the
`report_type` field was also confirmed present (line 27 of the same file, copied unmodified).

### Step 7 — sync, drift, harness

```
$ python3 tools/sync_native.py
synced v14/pentaho_reports/native
synced v15/pentaho_reports/native
synced v16/pentaho_reports/native
synced v17/pentaho_reports/native
synced v18/pentaho_reports/native
synced v19/pentaho_reports/native

$ python3 tools/check_drift.py
OK: all native copies identical to engine/native

$ tools/odoo_install_test.sh 14
--- v14: exit=0, test lines=19
RESULT v14 PASS
```

Log: `/private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/odoo-logs/odoo_v14.log`

Test summary lines from the log:
```
Module pentaho_reports loaded in 0.07s, 106 queries
Starting TestPentahoControllers.test_download_replays_pdf_and_sets_file_token_cookie ...
Starting TestPentahoControllers.test_download_requires_login ...
Starting TestPentahoControllers.test_preview_allows_report_author_without_admin ...
Starting TestPentahoControllers.test_preview_invalid_prpt_returns_safe_error ...
Starting TestPentahoControllers.test_preview_rejects_internal_user_without_technical_access ...
Starting TestPentahoControllers.test_preview_rejects_portal_user ...
Starting TestPentahoControllers.test_preview_renders_pdf_for_admin ...
Starting TestPentahoControllers.test_print_returns_inline_pdf ...
Starting TestPentahoRender.test_core_render_dispatch_finds_pentaho ...
Starting TestPentahoRender.test_create_forces_action_type ...
Starting TestPentahoRender.test_missing_file_raises_validation_error ...
Starting TestPentahoRender.test_render_report_custom_filename_strips_extension ...
Starting TestPentahoRender.test_render_report_rejects_non_pentaho_report ...
Starting TestPentahoRender.test_render_report_returns_pdf_tuple ...
Starting TestPentahoRender.test_render_report_zero_rows_still_pdf ...
15 post-tests in 0.71s, 398 queries
0 failed, 0 error(s) of 15 tests when loading database 'pentaho_test_v14'
```

No `ERROR`, `CRITICAL`, or `Traceback` lines anywhere in the log (grep confirmed
zero matches). No `AssetsBundle`/`web.assets_backend` error lines in the log
either (as expected — per the brief, HttpCase tests don't force-load the web
client JS bundle on this run, hence the separate `node --check`).

`node --check`:
```
$ node --check v14/pentaho_reports/static/src/js/action_manager.js && echo "node --check OK"
node --check OK
```
Syntax is valid; `node --version` on this machine is v24.3.0.

### Step 8 — commit

```
$ git add -A -- v14
$ git commit -m "v14: legacy ActionManager include, XML asset bundle

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
[feat/odoo-11-19-layout 86ffb3f] v14: legacy ActionManager include, XML asset bundle
 39 files changed, 4883 insertions(+)
```

`git status --short` after the commit: clean (nothing to commit, working tree clean).
Only `v14/` was staged and committed — no other repo files were touched.

## Self-review: `diff -r -x __pycache__ v15/pentaho_reports v14/pentaho_reports`

```
diff --color -r -x __pycache__ v15/pentaho_reports/README.md v14/pentaho_reports/README.md
1c1
< # pentaho_reports — Odoo 15
---
> # pentaho_reports — Odoo 14
4,5c4,5
< This folder is the Odoo **15** build; sibling folders `../v11` … `../v19` are the same module
< for other versions. Requires Python ≥ 3.7 (Odoo 15's own floor) and reportlab (bundled with Odoo).
---
> This folder is the Odoo **14** build; sibling folders `../v11` … `../v19` are the same module
> for other versions. Requires Python ≥ 3.6 (Odoo 14's own floor) and reportlab (bundled with Odoo).
7c7
< Install: copy this folder into your addons path (or `--addons-path=/path/to/v15`), then
---
> Install: copy this folder into your addons path (or `--addons-path=/path/to/v14`), then
diff --color -r -x __pycache__ v15/pentaho_reports/__manifest__.py v14/pentaho_reports/__manifest__.py
4c4
<     'version': '15.0.2.0.0',
---
>     'version': '14.0.2.0.0',
82a83
>         'views/assets.xml',
85,90d85
<     'assets': {
<         'web.assets_backend': [
<             'pentaho_reports/static/src/js/print_min.js',
<             'pentaho_reports/static/src/js/action_service.js',
<         ],
<     },
Only in v14/pentaho_reports/migrations: 14.0.2.0.0
Only in v15/pentaho_reports/migrations: 15.0.2.0.0
Only in v14/pentaho_reports/static/src/js: action_manager.js
Only in v15/pentaho_reports/static/src/js: action_service.js
Only in v14/pentaho_reports/views: assets.xml
```

This is exactly the expected diff set: manifest (version + assets→data), migrations
folder rename, README, `views/assets.xml` new, `action_service.js` removed /
`action_manager.js` added. Nothing else differs. `diff -r` on the migration file
contents (`post-migrate.py`) confirmed byte-identical (empty diff).

- Drift check: clean (`OK: all native copies identical to engine/native`).
- Leftover DBs: `psql -l | grep pentaho_test` → none (harness's `trap cleanup EXIT` dropped `pentaho_test_v14`).
- JS: passes `node --check`.
- `git status --short`: clean after commit.

## Files changed

- `v14/pentaho_reports/**` — new tree, copied from `v15/pentaho_reports` with the mechanical
  edits above (39 files, all listed in the commit).
- Notably: `v14/pentaho_reports/__manifest__.py`, `v14/pentaho_reports/README.md`,
  `v14/pentaho_reports/views/assets.xml` (new), `v14/pentaho_reports/static/src/js/action_manager.js`
  (new, `action_service.js` removed), `v14/pentaho_reports/migrations/14.0.2.0.0/post-migrate.py`.
- No files outside `v14/` were modified. `engine/native/` untouched; `sync_native.py` re-synced
  all vNN copies from it (no-op content changes, all already identical per drift check).

## Concerns

None outstanding. The one flagged deviation (Step 1's `CFLAGS` workaround for the reportlab
build) is a build-environment-only flag with no lasting effect on the repo or the venv beyond
the successfully installed `reportlab==3.5.55` package — matching the brief's expected version
exactly. All 15 module tests pass, drift is clean, the diff against v15 matches the prescribed
self-review shape exactly, and `node --check` confirms the legacy JS file is syntactically valid.

---

## Fix round 1 (task review findings)

The coordinator's review found the brief's JS itself (byte-identical to what was shipped)
had two real defects on Odoo 13/14 that would have propagated to v13/v12/v11 (the same
file family), plus one comment inaccuracy. All three addressed in
`v14/pentaho_reports/static/src/js/action_manager.js`:

1. **`.guardedCatch` never fires for our own `Error` throws.** Odoo 13/14's `guardedCatch`
   only invokes its handler when the rejection reason is NOT `instanceof Error` — but both
   of our explicit `throw new Error(...)` paths (report-not-found, no-data) are exactly
   that shape, so `framework.unblockUI()` was never reached on those paths and the throbber
   would hang forever. Fixed: `.guardedCatch(function (error) {` → `.catch(function (error) {`.

2. **Error text lost + core crash dialog still fires.** `_rpc` rejections carry the odoo
   error as `error.message` (an *object*, not a string), so the old `message` computation
   rendered `[object Object]`; and nothing called `error.event.preventDefault()`, so
   `ajax.js`'s own "Odoo Server Error" dialog still popped on top of our notification.
   Fixed: catch body now calls `error.event.preventDefault()` when present, and messages
   are built via a new `errorMessage(error)` helper that normalizes all three shapes we can
   receive (our own `Error`, an `_rpc` rejection `{message: <odoo error>, event}`, and a
   `session.get_file` parsed exception `{message, data: {message}}`).

3. **Header comment inaccuracy for 13/14.** The original comment said `session.get_file`
   "answers with the fileToken cookie that unblocks the UI" — true for the Odoo 11/12
   iframe-form variant, not for 12-14's XHR/blob download whose `complete` callback
   (`onloadend`) is what actually unblocks. Reworded per the review's exact wording.

### Verification

`node --check`:
```
$ node --check v14/pentaho_reports/static/src/js/action_manager.js && echo NODE_CHECK_OK
NODE_CHECK_OK
```

Node-side sanity check for `errorMessage` (written to scratchpad, not the repo, per
instruction — extracts the function body verbatim from the shipped file via regex, stubs
`_t` as identity, and asserts the four required cases):

```
$ node /private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/check_errorMessage.js v14/pentaho_reports/static/src/js/action_manager.js
PASS: own Error -> "x"
PASS: _rpc rejection (message is odoo error object) -> "real text"
PASS: session.get_file parsed exception -> "srv"
PASS: undefined -> "Unknown error"
```
(exit code 0 — all 4 pass)

Re-ran the full harness (drift + install/test) after the edit:
```
$ python3 tools/check_drift.py
OK: all native copies identical to engine/native

$ tools/odoo_install_test.sh 14
--- v14: exit=0, test lines=19
RESULT v14 PASS
```
Log tail:
```
15 post-tests in 0.59s, 402 queries
0 failed, 0 error(s) of 15 tests when loading database 'pentaho_test_v14'
```
No `ERROR`/`CRITICAL`/`Traceback` lines. No leftover `pentaho_test_*` databases
(`psql -l` clean — harness's `trap cleanup EXIT` dropped it). `git status --short`
clean after commit.

### Commit

```
2811238 v14: fix ActionManager error handling (guardedCatch, error text, crash dialog)
```
1 file changed (`v14/pentaho_reports/static/src/js/action_manager.js`), 25 insertions(+), 5 deletions(-).
Only this file was touched; no other repo files changed in this round.

### Concerns

None. All three review findings addressed exactly as specified, JS syntax and the
`errorMessage` logic are verified by the node-side checks above, and the Odoo 14 harness
still passes 15/15 tests.
