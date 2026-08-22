# Task 1 Report: Restructure the repo — v19/, engine/native/, sync + drift tools

Branch: `feat/odoo-11-19-layout`
Repo root: `/Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_odoo_workbench`
Commit: `b145ab14611cd591283aefcc579ecb2e757babb4` — "Restructure: v19/pentaho_reports, canonical engine/native, sync + drift tools"

All 9 steps in the brief were executed verbatim, from the repo root, with `pwd` verified first.

## Step 1 — Move the module and extract the engine (history-preserving)

Command run exactly as specified (`git mv pentaho_reports v19/pentaho_reports`, `git mv v19/pentaho_reports/native engine/native`, `git mv v19/pentaho_reports/PORT_CHANGES.md docs/PORT_CHANGES.md`, then pycache/pytest_cache cleanup).

Observed: `git status --short` showed 30 `R` (rename) lines, no deletions of content. Matches expected.

## Step 2 — Re-point the external convenience symlink

```
ln -sfn pentaho_odoo_workbench/v19/pentaho_reports /Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_reports
```
Observed: `lrwxr-xr-x ... pentaho_reports -> pentaho_odoo_workbench/v19/pentaho_reports`. Matches expected. (External to the repo, not committed.)

## Step 3 — `tools/sync_native.py`

Written verbatim from the brief. Copies `engine/native` into every existing `vNN/pentaho_reports/native`, plus `fixtures/partner_list.prpt` into `tests/fixtures/` if that fixture file exists at repo root (it currently does not — repo has no `fixtures/` dir yet, so that part is a no-op today, as designed).

## Step 4 — `tools/check_drift.py`

Written verbatim from the brief. `find_drift(repo)` returns a list of problem strings; `__main__` prints them, prints OK/DRIFT summary, exits 1 on drift / 0 clean.

## Step 5 — `engine/native/tests/test_no_drift.py`

Written verbatim from the brief. Walks up from the test file to find repo root (looks for `tools/check_drift.py` + `engine/native/`), imports `check_drift` from `tools/`, asserts `find_drift(repo) == []`. Skips if run outside the repo.

## Step 6 — Run sync, then drift

```
python3 tools/sync_native.py && python3 tools/check_drift.py
```
Observed:
```
synced v19/pentaho_reports/native
OK: all native copies identical to engine/native
```
Matches expected exactly. Only `v19/` exists so far (v11–v18 don't exist yet — that's Task 3+'s job); sync correctly skipped them since `module.is_dir()` is false for those.

## Step 7 — Prove drift is detected

```
echo "# drift" >> v19/pentaho_reports/native/fonts.py; python3 tools/check_drift.py; echo "exit=$?"; python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py
```
Observed:
```
v19: differs native/fonts.py
DRIFT: 1 problem(s)
exit=1
OK: all native copies identical to engine/native
```
Matches expected exactly (first run: `v19: differs native/fonts.py` + `exit=1`; second run after re-sync: OK).

## Step 8 — Run the engine test suite from its new home (baseline)

```
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q 2>&1 | tail -3; cd ../../..
```
Observed final line:
```
14 failed, 71 passed, 7 skipped, 1 warning, 12 errors in 0.95s
```
All 14 failures and 12 errors are `FileNotFoundError` for fixture files (verified by grepping full output — every FAILED/ERROR line is `FileNotFoundError: [Errno 2] No such file...`), matching the brief's "all failures/errors are FileNotFoundError for fixtures" description.

**Discrepancy from the brief's literal count, explained (not a bug):** the brief states "70 passed" but the observed run reports **71 passed**. The delta of exactly 1 is `test_no_drift.py::test_native_copies_do_not_drift`, which is itself a new passing test added by this task and lives inside `engine/native/tests/`, so a bare `pytest -q` run in that directory necessarily collects and counts it. Confirmed in isolation:
```
pytest -q -k test_no_drift  →  1 passed, 103 deselected, 1 warning in 0.12s
```
So: 70 pre-existing passes (unchanged) + 1 new `test_no_drift.py` pass = 71 total, and "`test_no_drift.py` passes" (the brief's second stated expectation) holds. The "1 warning" is a pre-existing `reportlab`/`ast.NameConstant` `DeprecationWarning` unrelated to this change (present before this task too — it comes from the `reportlab` library, not from any file touched here).

Failed/error counts (14 failed, 12 errors, 7 skipped) match the brief's numbers exactly. Per the task instructions, this FileNotFoundError baseline is expected and intentionally not fixed here (Task 2's job).

## Step 9 — Commit

```
git add -A && git commit -m "Restructure: v19/pentaho_reports, canonical engine/native, sync + drift tools

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```
Result: commit `b145ab1`, 54 files changed, 3414 insertions(+), 0 deletions. `git status --short` clean afterward.

## Files changed (summary)

- Renamed (git-tracked moves, history-preserving): `pentaho_reports/*` → `v19/pentaho_reports/*` (module code, controllers, migrations, models, static, tests, views); `pentaho_reports/native/*` → `engine/native/*` (8 source files + 8 test files); `pentaho_reports/PORT_CHANGES.md` → `docs/PORT_CHANGES.md`.
- New: `tools/sync_native.py`, `tools/check_drift.py`, `engine/native/tests/test_no_drift.py`.
- New (generated by `sync_native.py`, committed as plain new files rather than detected renames since it's a fresh copy of an existing tree): `v19/pentaho_reports/native/*` (16 files, engine + its own `tests/` subtree including the new `test_no_drift.py`).
- `.gitignore`: verified unchanged (already ignores `__pycache__/` and `.pytest_cache/`); confirmed via `git diff HEAD~1 HEAD -- .gitignore` (empty).
- External, not committed: `/Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_reports` symlink re-pointed to `pentaho_odoo_workbench/v19/pentaho_reports`.

## Self-review

- Read the full commit diffstat (`git show HEAD --stat`) — matches expectations: renames for the original module/engine files, `create mode` for the three new tool/test files and for the fresh `v19/pentaho_reports/native/` copy (git didn't detect the copy as a rename from `engine/native/`, which is normal/acceptable — content is byte-identical, confirmed by `check_drift.py` passing).
- Confirmed no unrelated files were reformatted: all three new files were written verbatim from the brief, byte-for-byte (diffed working copy against `git show HEAD:tools/sync_native.py`, identical).
- Confirmed `__pycache__`/`.pytest_cache` dirs were cleaned before commit (`find . -name __pycache__ ... -exec rm -rf`, `find . -name .pytest_cache ... -exec rm -rf`) and none leaked into the commit.
- Confirmed working tree is clean after commit (`git status --short` → empty).
- Confirmed `VERSIONS = list(range(11, 20))` (i.e., 11..19 inclusive) is defined identically in both `tools/sync_native.py` and `tools/check_drift.py`, per the brief's single-source-of-truth requirement.
- Confirmed the symlink step is correctly external to the repo and does not appear in `git status`.
- No repo-wide formatter was run; no files were touched beyond what the brief specifies.

## Concerns

- None blocking. The only notable item is the "70 passed" vs. observed "71 passed" in Step 8, fully explained above as an expected consequence of `test_no_drift.py` living inside the collected test directory — the underlying FileNotFoundError baseline (14 failed / 12 errors, all fixture-related) matches exactly, and this is explicitly the expected, not-yet-fixed baseline per the task instructions (Task 2 fixes fixtures).
- `fixtures/partner_list.prpt` does not yet exist at repo root, so the fixture-copy branch in `sync_native.py`/`check_drift.py` is currently a no-op (guarded by `.exists()` checks as designed) — this is expected since Task 1 doesn't create fixtures; presumably a later task adds it.

## Fix round 1 (post-review)

Reviewer's Important finding: `sync_native.py` copies `engine/native/tests/` into `v19/pentaho_reports/native/tests/` (and later into 8 more per-version copies). Neither `tests/` dir has `__init__.py` (intentional — tests do `from conftest import …`, relying on rootdir/`sys.path` insertion, which package-style collection via `__init__.py` would break). Without a scoping config, a bare `pytest -q` from the repo root would collect both `engine/native/tests/` and every `vNN/.../native/tests/` copy, hit duplicate basenames (e.g. two `test_bundle.py` in different dirs, same module name), and fail collection with "import file mismatch" — 8 collection errors, zero tests run. Per-directory runs were unaffected.

### What changed

1. **Added `pytest.ini` at repo root** (new file):
   ```ini
   [pytest]
   testpaths = engine/native/tests
   ```
   This scopes a bare `pytest`/`pytest -q` invocation from the repo root to only the canonical suite in `engine/native/tests/`, so per-version copies are never auto-collected. Did **not** add `__init__.py` files anywhere, per the reviewer's explicit instruction (would break the `conftest` import style the tests rely on).

2. **`chmod +x tools/sync_native.py tools/check_drift.py`** — both carry `#!/usr/bin/env python3` shebangs; made them executable to match. (Minor/cosmetic; the brief's own invocation is `python3 tools/sync_native.py`, so this was not required for correctness, only consistency.)

### Verification commands + output

Repo root, bare `pytest -q` (the exact scenario the reviewer flagged as broken):
```
cd /Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_odoo_workbench
/Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q 2>&1 | tail -20
```
Output (tail):
```
...
FAILED engine/native/tests/test_render.py::test_bir_2307_renders_background_image
ERROR engine/native/tests/test_bundle.py::test_si_query - FileNotFoundError: ...
14 failed, 71 passed, 7 skipped, 1 warning, 12 errors in 0.90s
```
No collection errors, no "import file mismatch". Only `engine/native/tests/` was collected (all reported paths are `engine/native/tests/...`). Counts match the Step 8 baseline exactly (71 passed = 70 pre-existing + `test_no_drift.py`, as already explained above; unchanged by this fix).

Per-directory run, still isolated and working:
```
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q 2>&1 | tail -3
```
Output:
```
ERROR test_bundle.py::test_si_query - FileNotFoundError: [Errno 2] No such fi...
14 failed, 71 passed, 7 skipped, 1 warning, 12 errors in 0.75s
```
Identical result running from within the tests directory itself — `pytest.ini`'s `testpaths` only affects invocations that don't specify explicit test paths/rootdir-relative args, so this mode of invocation (the brief's Step 8 command) is unaffected.

Executable bits confirmed:
```
ls -l tools/sync_native.py tools/check_drift.py
-rwxr-xr-x ... tools/check_drift.py
-rwxr-xr-x ... tools/sync_native.py
```

### Commit

```
git add -A && git commit -m "Restrict bare pytest to the canonical suite; make sync/drift scripts executable

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```
Result: commit `0b442c2` — "Restrict bare pytest to the canonical suite; make sync/drift scripts executable" — 3 files changed, 2 insertions(+) (`pytest.ini` created; two mode changes 100644 → 100755 for the tool scripts, no content changes). Working tree clean after commit.
