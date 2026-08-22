# Task 3 report: Port the engine to the Python 3.6 floor

## Summary

Ported `engine/native/` off `dataclasses` / `from __future__ import annotations` so it
imports and runs on Python 3.6.8 with reportlab 3.5.59 (Odoo 11's runtime), while keeping
it working on Python 3.12 / reportlab 4.1 (Task 2's floor). Public API (constructor
keyword args, attribute names, defaults, field-wise `==`) is unchanged. Also converted
`engine/native/tests/calibration.py` (not in the brief's explicit file list — see
"Finding not in the brief" below), since `tools/sync_native.py` copies the whole
`engine/native/tests/` tree, including that file, into `vNN/pentaho_reports/native/tests/`.

Commit: `6b7bd6b` — "engine: Python 3.6 floor (plain classes instead of dataclasses,
typing annotations)" on branch `feat/odoo-11-19-layout`.

## Step 1 — scratch venv

```
V=.../scratchpad/venvs
/Library/Frameworks/Python.framework/Versions/3.6/bin/python3 -m venv $V/py36-rl3559
$V/py36-rl3559/bin/python -m pip install -q --upgrade "pip<22"
$V/py36-rl3559/bin/python -m pip install -q "reportlab==3.5.59" "Pillow<9" "pytest<7.1" "pypdf<4"
$V/py36-rl3559/bin/python -c "import reportlab, pypdf, pytest, PIL; print(reportlab.Version)"
```
All installs succeeded via prebuilt wheels, no `--only-binary` needed. Output: `3.5.59` (matches expected).

## Step 2 — RED evidence

```
$ $V/py36-rl3559/bin/python -c "import sys; sys.path.insert(0,'engine'); import native.renderer" 2>&1 | tail -10
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "engine/native/renderer.py", line 8
    from __future__ import annotations
    ^
SyntaxError: future feature annotations is not defined
```
Exact match for the brief's expected error.

## Files changed

- `engine/native/model.py` — dataclasses replaced by the `_Record` base class + 7 plain
  classes (`BorderSide`, `Style`, `Element`, `Band`, `Group`, `PageDef`, `PlainParameter`),
  exactly as specified in the brief (field order, defaults, comments preserved next to
  each field).
- `engine/native/bundle.py`, `fonts.py`, `formats.py`, `query.py`, `renderer.py`,
  `painter.py` — `from __future__ import annotations` deleted; `typing` imports added
  (only the names each file needs: `Dict`/`List`/`Optional`/`Tuple`); every line the brief
  listed converted per the stated rules. Verified the pre-edit `grep -n` line numbers
  against the brief's list for every file — all matched exactly, no line-number drift.
- `engine/native/tests/calibration.py` — **not in the brief's file list**, fixed anyway
  (see finding below): 2 lines (`list[tuple[float, float, str]]` → `List[Tuple[float,
  float, str]]`, `list[dict]` → `List[dict]`) plus a `from typing import List, Tuple`.
- `engine/native/COMPAT.md` (new) — written verbatim from the brief.
- Mirrored into `v19/pentaho_reports/native/**` via `tools/sync_native.py`.

## GREEN evidence

**3.6 — compile/import:**
```
$ $V/py36-rl3559/bin/python -m compileall -q engine/native && echo COMPILE_OK
COMPILE_OK
$ $V/py36-rl3559/bin/python -c "import sys; sys.path.insert(0,'engine'); import native.renderer, native.bundle; print('IMPORT_OK')"
IMPORT_OK
```

**3.6 — full suite (post-sync, i.e. final state):**
```
$ cd engine/native/tests && $V/py36-rl3559/bin/python -m pytest -q
........................................................................ [ 63%]
..........................................                               [100%]
114 passed in 1.08s
```

**3.12 — full suite (odoo19 venv, reportlab 4.1, post-sync):**
```
$ cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q
114 passed, 1 warning in 0.66s
```
(The 1 warning is a pre-existing reportlab-internal `DeprecationWarning` about
`ast.NameConstant`, unrelated to this change.)

Both interpreters: same pass count as before (114), matching Task 2's baseline.

**3.12 — grep for modern syntax:**
```
$ grep -rn "from __future__\|dataclass\|| None\|list\[\|dict\[\|tuple\[" engine/native/*.py | grep -v "^\S*:\s*#"
engine/native/model.py:13:    """Minimal stand-in for @dataclass (the engine must import on Python 3.6):
engine/native/model.py:51:    __hash__ = None  # mutable, like an eq=True dataclass
engine/native/renderer.py:34:    """execute_query: callable(sql, params) -> list[dict] (one dict per row)."""
```
See "Discrepancy in Step 6's exact grep" below — these 3 lines are exactly the docstring/
comment prose the brief itself specifies verbatim (the `_Record` docstring, the `__hash__`
comment, and the `execute_query` docstring the brief explicitly says to leave). No live
syntax remains; confirmed by manual review of every changed file (see Self-Review).

## Sync + drift

```
$ python3 tools/sync_native.py
synced v19/pentaho_reports/native
$ python3 tools/check_drift.py
OK: all native copies identical to engine/native
```
(v11–v18 have no `pentaho_reports` module on disk yet, so only v19 is synced — expected,
matches `sync_native.py`'s own guard.)

Before syncing, `test_no_drift.py::test_native_copies_do_not_drift` failed on both
interpreters (113 passed / 1 failed = 114 total) — expected, since the v19 copy was still
the pre-conversion source until the sync ran. After `sync_native.py` + `check_drift.py`,
re-ran both suites and got clean 114/114 (shown above).

## Self-review

- Every dataclass replaced with identical field order and defaults: verified by diffing
  each class against the brief's given code block field-by-field (order, default value,
  `is_factory` flag, `_required` tuple) — all match, including the two-line split comment
  on `Element.kind` and the multi-line comment inside `Group._fields`.
- `from __future__ import annotations` removed from all 7 engine files (confirmed via
  `grep -rn "from __future__"` — zero hits).
- No remaining `X | None` / `list[...]` / `dict[...]` / `tuple[...]` as *live* annotations
  in any of the 7 files or `calibration.py` — remaining grep hits are exactly the 3
  docstring/comment lines discussed above (manually inspected, not evaluated by the
  interpreter).
- Both suites green with the identical pass count (114) on 3.6.8/reportlab 3.5.59 and
  3.12/reportlab 4.1.
- `git diff --stat` shows only the intended files touched (7 engine files + the
  `calibration.py` finding, mirrored into `v19/pentaho_reports/native/`, plus 2 new
  `COMPAT.md`); no incidental reformatting — diffs are line-for-line the annotation/import
  changes plus the model.py rewrite.
- Checked all seven model classes' construction sites in `bundle.py`, `renderer.py`,
  `painter.py`, and the test files: 100% keyword (or zero-arg) construction, so
  `_Record`'s positional-argument path, while implemented per the brief, is not exercised
  by any call site — consistent with the brief's own note that construction is
  keyword-only everywhere.
- Verified no other code depends on `dataclasses` module functions (`fields()`,
  `asdict()`, `replace()`) or `isinstance()` checks against the model classes that could
  behave differently now that they're plain classes — none found.

## Findings / discrepancies (both noted, neither blocking)

1. **`engine/native/tests/calibration.py` not in the brief's file list.** The brief's
   "Files" section lists only the 7 engine modules to modify. However
   `tools/sync_native.py` copies the entire `engine/native` tree (only excluding
   `__pycache__`/`*.pyc`/`.pytest_cache`/`.DS_Store`) into every `vNN/pentaho_reports/
   native`, including `tests/calibration.py`. That file used `list[tuple[float, float,
   str]]` and `list[dict]` return annotations (no `from __future__ import annotations`,
   relying on PEP 585 runtime generics, Python 3.9+), which broke test collection on 3.6
   with `TypeError: 'type' object is not subscriptable`. Since the global constraint
   states "`engine/native/**` Python floor is 3.6" (which covers the tests subtree) and
   Step 5 requires the full 114-test suite to pass on 3.6, I converted these 2 lines using
   the same rules as the rest of the task and noted it here rather than silently expanding
   scope without mention.
2. **Step 6's literal grep does not print `NO_MODERN_SYNTAX_LEFT`.** The brief's own
   verbatim code for `_Record`'s docstring ("Minimal stand-in for @dataclass...") and the
   `__hash__` comment ("mutable, like an eq=True dataclass"), plus the explicit instruction
   to leave `renderer.py`'s `execute_query` docstring ("...-> list[dict]...") unconverted,
   guarantee 3 grep hits against the pattern `dataclass\|list\[` — the given
   `grep -v "^\S*:\s*#"` filter only strips full-line comments (content starting with `#`
   after whitesp) and does not touch docstring lines or inline trailing comments, so it
   cannot filter these out. I ran the exact command as specified (see GREEN evidence
   above) and report its real output rather than the literal string
   `NO_MODERN_SYNTAX_LEFT`, since faking that output would misrepresent the evidence. I
   manually confirmed (Self-Review) that no executable code uses old-style annotations
   anywhere in the changed files.
3. **`COMPAT.md` references `tools/test_matrix.sh` and `tools/engine_matrix.sh`.** Neither
   script exists yet in `tools/` — written verbatim from the brief regardless, since these
   are presumably deliverables of a later task in this SDD plan (test-matrix / cross-
   version CI tooling). Not a blocker for this task; flagging so the controller/reviewer
   is aware the doc currently references not-yet-built tooling.

## Concerns

None blocking. The two documentation-only grep-pattern hits and the pre-existing (unbuilt)
`tools/test_matrix.sh`/`tools/engine_matrix.sh` references are noted above for visibility,
not because they indicate incorrect code.
