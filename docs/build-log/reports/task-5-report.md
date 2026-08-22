# Task 5 Report: `partner_list.prpt` fixture

## Status: DONE

## What was implemented

1. **`engine/native/tests/test_partner_list.py`** — written verbatim from the brief's Step 1. Two tests:
   - `test_partner_list_query_targets_res_partner_only` — asserts the bundle's SQL targets `res_partner`, never `sale_order`, and preserves the `${ids}` placeholder.
   - `test_partner_list_renders_pdf_with_stub_rows` — renders the fixture end-to-end with a stub `execute_query` callback and asserts a `%PDF`-prefixed output, exactly one query call, and `res_partner` in the executed SQL.

2. **`fixtures/partner_list.prpt`** — generated via `tools/scrub_fixture.py` from `fixtures/evergood_sale_report.prpt`, with the root query rewritten to:
   ```
   select rp.id as so_no, rp.name as partner from res_partner rp where rp.id in (${ids}) order by rp.id
   ```
   and the layout title label rewritten to `Partner List`. Credentials scrubbed identically to the other 8 fixtures (user=demo, password empty, url=`jdbc:postgresql://localhost/demo`, hostname=localhost, database-name=demo).

3. Synced into `v19/pentaho_reports/native/tests/test_partner_list.py` and `v19/pentaho_reports/tests/fixtures/partner_list.prpt` via `tools/sync_native.py`.

## RED evidence (Step 2 — fixture absent before generation)

```
$ cd engine/native/tests && .../venv/bin/python -m pytest -q test_partner_list.py
ss                                                                       [100%]
2 skipped, 1 warning in 0.07s
```
Matches expected `2 skipped` (conftest's `_FixturePath.read_bytes()` skips when the fixture file doesn't exist yet).

## Step 3 — fixture generation, printed query + label check

```
$ python3 tools/scrub_fixture.py fixtures/evergood_sale_report.prpt fixtures/partner_list.prpt \
  --query 'select rp.id as so_no, rp.name as partner from res_partner rp where rp.id in (${ids}) order by rp.id' \
  --label 'Partner List'
wrote fixtures/partner_list.prpt

$ python3 - <<'PY'
import zipfile; z=zipfile.ZipFile("fixtures/partner_list.prpt")
print(z.read("datasources/sql-ds.xml").decode().split("<data:static-query>")[1].split("</data:static-query>")[0])
print("Partner List" in z.read("layout.xml").decode())
PY
select rp.id as so_no, rp.name as partner from res_partner rp where rp.id in (${ids}) order by rp.id
True
```
`${ids}` survived intact (tool only escapes `& < >`); label check printed `True`.

## GREEN evidence (Step 4)

```
$ cd engine/native/tests && .../venv/bin/python -m pytest -q test_partner_list.py test_fixtures_scrubbed.py
............                                                             [100%]
12 passed, 1 warning in 0.06s
```

Full engine suite (all files in `engine/native/tests/`):
```
$ .../venv/bin/python -m pytest -q .
........................................................................ [ 62%]
............................................                             [100%]
116 passed, 1 warning in 0.63s
```
Confirms 114 (baseline) + 2 (new) = 116 passed, no regressions.

## Sync + drift

```
$ python3 tools/sync_native.py
synced v19/pentaho_reports/native

$ python3 tools/check_drift.py
OK: all native copies identical to engine/native

$ ls v19/pentaho_reports/tests/fixtures/
partner_list.prpt
```
Both exit 0. `v19/pentaho_reports/tests/fixtures/partner_list.prpt` present as required by later Odoo-module-level tasks.

## Files changed

- `engine/native/tests/test_partner_list.py` (new, canonical)
- `fixtures/partner_list.prpt` (new, generated/scrubbed)
- `v19/pentaho_reports/native/tests/test_partner_list.py` (new, synced copy)
- `v19/pentaho_reports/tests/fixtures/partner_list.prpt` (new, synced copy)

No other tracked files were modified — `fixtures/README.md` already documented the `partner_list.prpt` row prior to this task (pre-existing, untouched).

## Commit

`733badc` — "fixtures: synthetic partner_list.prpt for the Odoo module tests" (4 files changed, 54 insertions, all creates). Trailer lines match the brief exactly.

## Self-review

- Test file matches the brief's Step 1 code verbatim (byte-for-byte, including docstring wording). Confirmed.
- Fixture query correct: targets `res_partner` only, `sale_order` absent, `${ids}` placeholder intact. Confirmed via both the printed Step 3 output and `test_partner_list_query_targets_res_partner_only`.
- Label correctly rewritten to `Partner List` (`True` printed at Step 3, and `layout.xml` fields `so_no`/`partner` untouched — same field names as the parent `evergood_sale_report.prpt`).
- Full engine suite green: 116 passed (was 114 before this task, +2 new tests, 0 regressions).
- `sync_native.py` and `check_drift.py` both clean; `v19/pentaho_reports/tests/fixtures/partner_list.prpt` present.
- Credentials scrubbed identically to the other 8 fixtures (verified by reading `datasources/sql-ds.xml` directly, and by `test_fixtures_scrubbed.py` passing).
- `git status` after commit: clean tree, only the 4 expected new files added — no unrelated reformatting or drift.
- `engine/native/tests/test_partner_list.py` uses no Python-3.6-incompatible syntax (no `X | None`, no `list[str]`, no walrus; only f-string-free plain code, matching the brief verbatim anyway).

## Concerns

None. All steps completed exactly as specified, all evidence matches expected output, commit trailers match the brief.
