# Task 2 Report: Vendor credential-scrubbed fixtures, self-contained engine tests

## Status: DONE

## What was implemented

Followed the brief's 9 steps in order (TDD: scrub test + conftest first, observe
skips, then vendor).

1. **`engine/native/tests/test_fixtures_scrubbed.py`** — created verbatim from the
   brief: `test_all_expected_fixtures_present`, parametrized
   `test_fixture_has_no_credentials` (8 fixtures), `test_mimetype_is_first_and_stored`.
2. **`engine/native/tests/conftest.py`** — rewritten verbatim from the brief:
   `_find_fixtures_dir()` (checks `$PENTAHO_FIXTURES`, else walks ancestors for a
   `fixtures/` dir containing `delivery_receipt.prpt`), `_FixturePath` (a `Path`
   subclass whose `.read_bytes()` calls `pytest.skip(...)` when the file is absent),
   `fixture_path()`, and all nine constants (`DELIVERY_RECEIPT_PRPT`,
   `SALES_INVOICE_PRPT`, `AP_VOUCHER_PRPT`, `BIR_2307_PRPT`,
   `EVERGOOD_SALE_REPORT_PRPT`, `GL_LISTING_NESTED_PRPT`, `PRINT_SUPPLIER_CHECK_PRPT`,
   `BARCODE_PRPT`, `PARTNER_LIST_PRPT`) plus `FIXTURES_DIR`.
3. **`engine/native/tests/test_date_field.py`** — replaced the `MODULE_DIR`-derived
   `CHECK_VOUCHER_PRPT` path and its `pytestmark = pytest.mark.skipif(...)` block with
   `from conftest import PRINT_SUPPLIER_CHECK_PRPT` / `CHECK_VOUCHER_PRPT =
   PRINT_SUPPLIER_CHECK_PRPT` (comment above the constant kept).
4. **`engine/native/tests/test_preview_render.py`** — same pattern:
   `from conftest import EVERGOOD_SALE_REPORT_PRPT`, `SALE_REPORT_PRPT =
   EVERGOOD_SALE_REPORT_PRPT`, `pytestmark` block deleted.
5. **`tools/scrub_fixture.py`** — created verbatim from the brief: CLI
   (`SRC DEST [--query SQL] [--label TEXT]`) and importable `scrub(src, dest, query,
   label)`. Scrubs every `*sql-ds.xml` part (user→`demo`, password→empty,
   url→`jdbc:postgresql://localhost/demo`, `::pentaho-reporting::hostname`→`localhost`,
   `::pentaho-reporting::name`/`::pentaho-reporting::database-name`→`demo`); only the
   root `datasources/sql-ds.xml` gets an optional `--query` rewrite (nested
   `subreport*/datasources/sql-ds.xml` parts are scrubbed only, never query-rewritten);
   `mimetype` is written first and `ZIP_STORED`; all other parts pass through
   byte-for-byte (deflated).
6. **Vendored the 8 fixtures** with `tools/scrub_fixture.py` from
   `/Volumes/Workspace/Development/Workbench/pentaho-report-designer/sample_prpt/`
   (read-only, untouched) into `fixtures/`.
7. **`fixtures/README.md`** — created verbatim from the brief (includes the
   `partner_list.prpt` row for Task 5, per the brief's exact text — that file does not
   exist yet and no test references it in this task).
8. Ran the full suite — 0 failed, 0 errors, all fixture-backed tests now pass.
9. `tools/sync_native.py` → `tools/check_drift.py` (clean) → committed.

## TDD evidence

**RED** (after Step 2/3, before vendoring — `engine/native/tests`, fixtures absent):
```
1 failed, 70 passed, 43 skipped, 1 warning in 0.35s
```
The single failure was `test_no_drift.py::test_native_copies_do_not_drift` — expected,
since `engine/native` (just edited) hadn't been synced to `v19/pentaho_reports/native`
yet. All 43 skips were clean `pytest.skip(...)` calls (fixture-backed tests), zero
`FileNotFoundError`s — confirming the RED state is "skip cleanly," not "error."

**GREEN** (after Step 6 vendoring, before sync — `engine/native/tests`):
```
1 failed, 113 passed, 1 warning in 0.69s
```
Again the sole failure was the pre-sync drift check; every fixture-backed test
(including all 10 new scrub tests) passed.

**GREEN, final** (after `sync_native.py` + `check_drift.py`, bare `pytest -q` from repo
root):
```
114 passed, 1 warning in 0.93s
```
0 failed, 0 errors, 0 skipped. `python3 tools/check_drift.py` → `OK: all native copies
identical to engine/native`.

### Note on Step 8's expected skip count

The brief's Step 8 says skips should drop to "the 7 pre-existing skips (+1 for
`partner_list.prpt`, created in Task 5)". The actual observed result is **0 skips**:
the pre-existing 7 skips (in `test_bundle.py`, guarded by inline
`if not X.exists(): pytest.skip(...)`) were against `GL_LISTING_NESTED_PRPT` and
`BARCODE_PRPT`, which pointed at a repo-root `sample_prpt/` directory that does not
exist in this checkout (the original conftest computed `SAMPLE_PRPT_DIR =
PIAGGIO_DIR.parent / "sample_prpt"`, but no such directory is tracked in this repo —
`sample_prpt` only exists in the sibling source directory). Now that both fixtures are
vendored into `fixtures/`, those tests find them and pass instead of skipping. No test
references `PARTNER_LIST_PRPT` yet (confirmed by `grep`), so no skip is added for it —
consistent with the task instructions' note that this is expected in Task 2.

## `du -ch` total

```
296K	total
```
(8 files, largest is `BIR_2307.prpt` at 231K due to an embedded background image;
under the brief's 300 KB budget.)

## Files changed

- Created: `tools/scrub_fixture.py`, `fixtures/README.md`, `fixtures/delivery_receipt.prpt`,
  `fixtures/sales_invoice.prpt`, `fixtures/ap_voucher.prpt`, `fixtures/BIR_2307.prpt`,
  `fixtures/evergood_sale_report.prpt`, `fixtures/gl_listing_nested.prpt`,
  `fixtures/print_supplier_check.prpt`, `fixtures/product_barcode.prpt`,
  `engine/native/tests/test_fixtures_scrubbed.py` (+ synced copy in
  `v19/pentaho_reports/native/tests/`)
- Modified: `engine/native/tests/conftest.py`, `engine/native/tests/test_date_field.py`,
  `engine/native/tests/test_preview_render.py` (+ synced copies in
  `v19/pentaho_reports/native/tests/`)

Commit: `6e8a79e` — "Vendor credential-scrubbed .prpt fixtures; engine tests
self-contained" (18 files changed, 328 insertions(+), 68 deletions(-)).

## Self-review findings

- Confirmed `engine/native/tests/conftest.py` and
  `v19/pentaho_reports/native/tests/conftest.py` are byte-identical after sync (`diff`
  → no output), same for `test_fixtures_scrubbed.py`.
- Confirmed `scrub_fixture.py` matches the brief exactly: root-only query rewrite
  (`query if name == "datasources/sql-ds.xml" else None`), `mimetype` written first
  with `ZIP_STORED`, all other parts `ZIP_DEFLATED`.
- Inspected `fixtures/BIR_2307.prpt`'s three `sql-ds.xml` parts (root +
  `subreport1/` + `subreport/`) directly: all three show `user=demo`, empty
  `password`, `url=jdbc:postgresql://localhost/demo`, `hostname=localhost`,
  `name=demo`, `database-name=demo`. No `--query`/`--label` was passed for any of the
  8 direct copies (only used for Task 5's synthetic `partner_list.prpt`), so each
  report's original business SQL (joins against `account_move`, `res_partner`, etc.)
  is preserved untouched — that SQL carries no credentials.
- All 10 `test_fixtures_scrubbed.py` tests pass individually
  (`pytest engine/native/tests/test_fixtures_scrubbed.py -v` → `10 passed`).
- Verified source `.prpt` files in `sample_prpt/` were only read, never modified
  (no writes attempted there).
- `git status` after commit: clean working tree; `git diff --stat` before commit
  showed exactly the files the brief's "Files" section named (plus their `v19` synced
  twins, which the brief's own sync step produces).
- Ran the two exact verification commands from the brief (`cd engine/native/tests &&
  ... pytest -q` and bare `pytest -q` from repo root) — both give `114 passed`.
- Also tried running pytest directly inside
  `v19/pentaho_reports/native/tests/` (not a brief-required check): it errors on
  collection because `v19/pentaho_reports/__init__.py` imports `odoo` when pytest's
  package-rootdir discovery walks up through it. This is pre-existing behavior from
  Task 1's addon structure (that suite is meant to run inside a live Odoo /
  `odoo-bin --test-enable`, not bare `pytest`), not something introduced by this task,
  and out of scope for Task 2 — the root `pytest.ini` intentionally scopes bare
  `pytest` to `engine/native/tests` for exactly this reason.

## Concerns

- None blocking. The only deviation from the brief's literal text is the Step 8
  skip-count expectation (0 observed vs. "7 pre-existing"), which is explained above
  and was flagged in advance by the task instructions as a likely discrepancy to
  report rather than treat as a defect.
