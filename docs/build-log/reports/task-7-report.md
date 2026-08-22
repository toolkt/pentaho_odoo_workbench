# Task 7 report — v18 and v17 (family C minus the `jsonrpc` route)

Commit: `3b86956` — "v17, v18: same as v19 with type='json' preview route"

## What was implemented

Followed the brief's three steps verbatim, no adaptations needed.

1. **Step 1 — copy + edit**, for `N in 18 17`:
   - `rm -rf vN && mkdir -p vN && cp -R v19/pentaho_reports vN/pentaho_reports`
   - Pruned `__pycache__` dirs from the fresh copy.
   - `sed -i ''` on `__manifest__.py`: `'version': '19.0.2.0.0'` → `'version': 'N.0.2.0.0'`.
   - `sed -i ''` on `controllers/main.py`: `@http.route('/pentaho/preview', type='jsonrpc', auth='user')` → `type='json'`.
   - `mv migrations/19.0.2.0.0 → migrations/N.0.2.0.0`.
   - `sed -i ''` on `README.md`: title, sibling-folder list, Python-floor sentence, `--addons-path` example — all four substitutions from the brief.
   - Verified each with the brief's own grep/ls after every substitution — all matched on the first try; no hand-editing was needed (README wording matched the brief's sed patterns exactly for both versions).

2. **Step 2 — sync, drift, run both Odoos**:
   - `python3 tools/sync_native.py` → synced `native/` into v17, v18, v19 (only these three version folders exist yet; v11-v16 are other tasks not yet run).
   - `python3 tools/check_drift.py` → `OK: all native copies identical to engine/native`.
   - `tools/odoo_install_test.sh 18` → `RESULT v18 PASS`.
   - `tools/odoo_install_test.sh 17` → `RESULT v17 PASS`.

3. **Step 3 — commit** — exact message from the brief, trailers included.

## Harness output

```
$ python3 tools/sync_native.py >/dev/null
synced v17/pentaho_reports/native
synced v18/pentaho_reports/native
synced v19/pentaho_reports/native

$ python3 tools/check_drift.py
OK: all native copies identical to engine/native

$ tools/odoo_install_test.sh 18
--- v18: exit=0, test lines=28
RESULT v18 PASS

$ tools/odoo_install_test.sh 17
--- v17: exit=0, test lines=22
RESULT v17 PASS
```

Test summary lines from each log:
```
odoo_v18.log:
  odoo.tests.stats: pentaho_reports: 19 tests 0.42s 360 queries
  odoo.tests.result: 0 failed, 0 error(s) of 15 tests when loading database 'pentaho_test_v18'

odoo_v17.log:
  odoo.tests.stats: pentaho_reports: 19 tests 1.11s 416 queries
  odoo.tests.result: 0 failed, 0 error(s) of 15 tests when loading database 'pentaho_test_v17'
```
(15 module tests each — 8 `TestPentahoControllers` + 7 `TestPentahoRender` — same set both versions; the "19 tests" in `odoo.tests.stats` counts sub-timed segments, matching the pattern already seen on v19's own report.) Known v18 difference (`res.users.groups_id`) exercised without incident — the tests' own feature-detection handled it; no log warnings/errors related to it.

Both runs exited 0, and the harness's own `trap cleanup EXIT` dropped `pentaho_test_v18` / `pentaho_test_v17` on completion.

## Self-review

### `diff -r v19/pentaho_reports v18/pentaho_reports` (after pruning `__pycache__`, which is gitignored and was only a runtime byproduct of running the test harness — not part of the copy)

```
Files v19/pentaho_reports/README.md and v18/pentaho_reports/README.md differ
Files v19/pentaho_reports/__manifest__.py and v18/pentaho_reports/__manifest__.py differ
Files v19/pentaho_reports/controllers/main.py and v18/pentaho_reports/controllers/main.py differ
Only in v18/pentaho_reports/migrations: 18.0.2.0.0
Only in v19/pentaho_reports/migrations: 19.0.2.0.0
```

Content of each diff (confirmed single-line/expected-only changes):
```
__manifest__.py:
4c4
<     'version': '19.0.2.0.0',
---
>     'version': '18.0.2.0.0',

controllers/main.py:
18c18
<     @http.route('/pentaho/preview', type='jsonrpc', auth='user')
---
>     @http.route('/pentaho/preview', type='json', auth='user')

README.md:
1c1
< # pentaho_reports — Odoo 19
---
> # pentaho_reports — Odoo 18
4,5c4,5
< This folder is the Odoo **19** build; sibling folders `../v11` … `../v18` are the same module
< for other versions. Requires Python ≥ 3.10 (Odoo 19's own floor) and reportlab (bundled with Odoo).
---
> This folder is the Odoo **18** build; sibling folders `../v11` … `../v19` are the same module
> for other versions. Requires Python ≥ 3.10 (Odoo 18's own floor) and reportlab (bundled with Odoo).
7c7
< Install: copy this folder into your addons path (or `--addons-path=/path/to/v19`), then
---
> Install: copy this folder into your addons path (or `--addons-path=/path/to/v18`), then
```
`diff -r v19/pentaho_reports/migrations/19.0.2.0.0 v18/pentaho_reports/migrations/18.0.2.0.0` — empty (content identical, only the folder name differs).

### `diff -r v19/pentaho_reports v17/pentaho_reports`

Identical shape, with `17` substituted throughout:
```
Files v19/pentaho_reports/README.md and v17/pentaho_reports/README.md differ
Files v19/pentaho_reports/__manifest__.py and v17/pentaho_reports/__manifest__.py differ
Files v19/pentaho_reports/controllers/main.py and v17/pentaho_reports/controllers/main.py differ
Only in v17/pentaho_reports/migrations: 17.0.2.0.0
Only in v19/pentaho_reports/migrations: 19.0.2.0.0
```
Same four single-purpose content diffs (version, route type, README text) as v18; migrations content diff empty.

Nothing else differs in either version — confirmed the diff-only categories are exactly: manifest version line, route type line, migrations folder name, README text. No native/, tests/, models/, views/, static/ changes.

### Drift and leftover DBs

- `python3 tools/check_drift.py` (re-run after the self-review pycache cleanup) → `OK: all native copies identical to engine/native`.
- `psql -tAc "select datname from pg_database where datname like 'pentaho_test%'" postgres` → empty result, no leftover throwaway DBs.
- `git status --short` before commit showed only `?? v17/` and `?? v18/` (nothing else touched); after commit, clean.

## Files changed

- `v18/pentaho_reports/**` (new — full copy of v19 with manifest version, route type, migrations folder name, README text updated)
- `v17/pentaho_reports/**` (new — same)

76 files created total (38 per version), matching v19's own file count exactly.

## Concerns

None. All three sed-based edit steps matched the brief's grep verification on the first attempt for both versions — no hand-editing of the README or any other file was required. Both Odoo harness runs passed cleanly on the first try (no glue-code fixes needed for 18 or 17). Drift check clean, no leftover DBs, commit message matches the brief exactly including trailers.
