# `pentaho_reports` for Odoo 11 → 19 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single Odoo-19 `pentaho_reports` module into nine self-contained per-version folders `v11/pentaho_reports` … `v19/pentaho_reports` sharing one Python-3.6-compatible engine, each proven by installing and testing on the matching local Odoo.

**Architecture:** The Odoo-independent engine moves to `engine/native/` (canonical) and is copied byte-identically into every `vNN/pentaho_reports/native/` by `tools/sync_native.py`, guarded by `tools/check_drift.py`. The ~600-line Odoo glue (manifest, model, controller, views, JS, tests) exists per version in three families: legacy web client (v11–v14), OWL registry + `attrs` views (v15–v16), OWL registry + Python-expression views (v17–v19). Verification is a matrix: drift → per-folder `compileall` with that Odoo's venv → engine pytest across interpreter × reportlab pins → real install + module tests on throwaway DBs `pentaho_test_vNN`.

**Tech Stack:** Python 3.6–3.12, reportlab 3.5–5.0, Odoo 11–19 (local trees at `/Volumes/Workspace/Development/OdooWorkbench/odooNN/{odoo,venv}`), pytest, PostgreSQL 17 (Postgres.app; `bem` is superuser, roles `odoo11`…`odoo19` exist, trust auth on localhost, no CREATEDB).

**Spec:** `docs/superpowers/specs/2026-08-21-per-version-layout-design.md` — read it first. Per-version Odoo API facts with `file:line` evidence: `docs/superpowers/specs/2026-08-21-odoo-version-api-survey.md` (271 KB; grep it for the version you are working on).

## Global Constraints

- Repo root: `/Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_odoo_workbench` (git, branch `main`). **Run every command from the repo root; verify with `pwd` first.** Never `cd` into `.worktrees` or other repos.
- **Python floor for `engine/native/` is 3.6.** No `dataclasses`, no `from __future__ import annotations`, no `X | None`, no `list[str]`/`dict[...]`/`tuple[...]` in evaluated annotations, no walrus, no `removeprefix`, no `functools.cached_property`, no positional-only params. f-strings are allowed. Enforced by `python3.6 -m compileall` and the scratch-venv matrix.
- Module glue for v11 must also be Python-3.6 clean (it runs on Odoo 11's 3.6.8 venv). f-strings are fine there too.
- `_()` translations: **single argument + `%`**, i.e. `_('msg %s') % x`, never `_('msg %s', x)` (Odoo 11–13 TypeError otherwise). The module already follows this.
- Interpreters: py3.6 `/Library/Frameworks/Python.framework/Versions/3.6/bin/python3`; py3.9 `/opt/homebrew/bin/python3.9`; py3.10 `/opt/homebrew/bin/python3.10`; py3.12 `/opt/homebrew/bin/python3.12`. Odoo venvs: `/Volumes/Workspace/Development/OdooWorkbench/odooNN/venv/bin/python`.
- Scratch venvs go under `/private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/venvs/`. **Never `pip install` into an Odoo venv** except the one explicitly required fix: `odoo14/venv` gets `reportlab==3.5.55`.
- Throwaway Odoo databases are named `pentaho_test_vNN`, created by `createdb -O odooNN`, and **always dropped** after the run (also on failure).
- HTTP port for test runs: `180NN` (18011 … 18019) — verified free.
- Fixture `.prpt` files committed to the repo must have credentials scrubbed (user `demo`, empty password, url `jdbc:postgresql://localhost/demo`). A test enforces this.
- Commit after every task with the trailer lines:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC
  ```
- Do not reformat files you did not otherwise change. Do not run repo-wide formatters.

---

## File structure (end state)

```
pentaho_odoo_workbench/
├── README.md                                   root docs: version matrix, install, floor, tooling
├── .gitignore
├── docs/
│   ├── PORT_CHANGES.md                         (moved from pentaho_reports/)
│   └── superpowers/{specs,plans}/
├── engine/
│   └── native/                                 canonical engine (import name `native`)
│       ├── __init__.py bundle.py fonts.py formats.py model.py painter.py query.py renderer.py
│       ├── COMPAT.md                           the 3.6 rule
│       └── tests/ conftest.py test_*.py calibration.py test_no_drift.py test_fixtures_scrubbed.py
├── fixtures/                                   delivery_receipt.prpt sales_invoice.prpt ap_voucher.prpt BIR_2307.prpt
│   │                                           evergood_sale_report.prpt gl_listing_nested.prpt print_supplier_check.prpt
│   │                                           product_barcode.prpt partner_list.prpt README.md
├── tools/
│   ├── sync_native.py        engine/native → vNN/pentaho_reports/native; fixtures/partner_list.prpt → vNN/.../tests/fixtures/
│   ├── check_drift.py        exit 1 on any difference
│   ├── scrub_fixture.py      scrub creds (+ optional --query/--label rewrite) → used for vendoring and partner_list
│   ├── engine_matrix.sh      scratch venvs × reportlab pins → pytest engine/native/tests
│   ├── odoo_install_test.sh  NN → createdb, odoo-bin -i pentaho_reports --test-enable, scan log, dropdb
│   └── test_matrix.sh        drift → compileall per folder → engine_matrix → odoo_install_test 11..19
└── vNN/pentaho_reports/  (N = 11..19)
    ├── __init__.py __manifest__.py README.md
    ├── controllers/{__init__,main}.py
    ├── models/{__init__,ir_actions_report}.py
    ├── views/report_views.xml  (+ views/assets.xml on v11–v14)
    ├── static/description/{icon.png,index.html}  static/src/js/{print_min.js, action_service.js | action_manager.js}
    ├── migrations/NN.0.2.0.0/post-migrate.py
    ├── tests/{__init__,test_render,test_controllers}.py  tests/fixtures/partner_list.prpt
    └── native/                                 synced copy (never edit here)
```

---

### Task 1: Restructure the repo — `v19/`, `engine/native/`, sync + drift tools

**Files:**
- Move: `pentaho_reports/` → `v19/pentaho_reports/` ; `v19/pentaho_reports/native/` → `engine/native/` ; `v19/pentaho_reports/PORT_CHANGES.md` → `docs/PORT_CHANGES.md`
- Create: `tools/sync_native.py`, `tools/check_drift.py`, `engine/native/tests/test_no_drift.py`
- Modify: `.gitignore` (no change needed; verify it ignores `__pycache__/` and `.pytest_cache/` — it does)
- External (not in repo): re-point symlink `/Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_reports` → `pentaho_odoo_workbench/v19/pentaho_reports`

**Interfaces:**
- Produces: `tools/sync_native.py` (CLI, no args; `python3 tools/sync_native.py`) and `tools/check_drift.py` (CLI; exit 0 clean / 1 drift; importable `check_drift.find_drift(repo_root: Path) -> list[str]`). `VERSIONS = [11, …, 19]` is defined in both and is the single list later tasks extend nothing in (all nine exist from the start; missing `vNN` folders are skipped by sync and reported by drift only if the folder exists without a `native/`).

- [ ] **Step 1: Move the module and extract the engine (history-preserving)**

```bash
cd /Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_odoo_workbench && pwd
mkdir -p v19 engine docs
git mv pentaho_reports v19/pentaho_reports
git mv v19/pentaho_reports/native engine/native
git mv v19/pentaho_reports/PORT_CHANGES.md docs/PORT_CHANGES.md
find . -name __pycache__ -type d -prune -exec rm -rf {} + ; find . -name .pytest_cache -type d -prune -exec rm -rf {} +
git status --short | head -20
```
Expected: renames listed (R), no deletions of content.

- [ ] **Step 2: Re-point the external convenience symlink**

```bash
ln -sfn pentaho_odoo_workbench/v19/pentaho_reports /Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_reports
ls -l /Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_reports
```

- [ ] **Step 3: Write `tools/sync_native.py`**

```python
#!/usr/bin/env python3
"""Copy the canonical engine (engine/native) into every vNN/pentaho_reports/native.

Also copies fixtures/partner_list.prpt into vNN/pentaho_reports/tests/fixtures/.
Idempotent. Run from anywhere; paths are resolved relative to this file.
"""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "engine" / "native"
FIXTURE = REPO / "fixtures" / "partner_list.prpt"
VERSIONS = list(range(11, 20))
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".DS_Store")


def sync(repo: Path = REPO) -> list:
    synced = []
    for n in VERSIONS:
        module = repo / ("v%d" % n) / "pentaho_reports"
        if not module.is_dir():
            continue
        target = module / "native"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ENGINE, target, ignore=IGNORE)
        if FIXTURE.exists():
            dest = module / "tests" / "fixtures" / FIXTURE.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FIXTURE, dest)
        synced.append(str(target.relative_to(repo)))
    return synced


if __name__ == "__main__":
    for t in sync():
        print("synced", t)
    sys.exit(0)
```

- [ ] **Step 4: Write `tools/check_drift.py`**

```python
#!/usr/bin/env python3
"""Fail if any vNN/pentaho_reports/native differs from engine/native
(or any vNN/.../tests/fixtures/partner_list.prpt differs from fixtures/).

Exit 0 = identical, 1 = drift (first differences printed).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VERSIONS = list(range(11, 20))
SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def _files(root: Path) -> dict:
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and not (SKIP_PARTS & set(p.parts)) and p.suffix != ".pyc" and p.name != ".DS_Store":
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


def find_drift(repo: Path = REPO) -> list:
    engine = _files(repo / "engine" / "native")
    fixture = repo / "fixtures" / "partner_list.prpt"
    problems = []
    for n in VERSIONS:
        module = repo / ("v%d" % n) / "pentaho_reports"
        if not module.is_dir():
            continue
        copy_dir = module / "native"
        if not copy_dir.is_dir():
            problems.append("v%d: native/ missing" % n)
            continue
        copy = _files(copy_dir)
        for rel in sorted(set(engine) | set(copy)):
            if rel not in copy:
                problems.append("v%d: missing native/%s" % (n, rel))
            elif rel not in engine:
                problems.append("v%d: extra native/%s" % (n, rel))
            elif engine[rel] != copy[rel]:
                problems.append("v%d: differs native/%s" % (n, rel))
        if fixture.exists():
            dest = module / "tests" / "fixtures" / fixture.name
            if not dest.exists():
                problems.append("v%d: missing tests/fixtures/partner_list.prpt" % n)
            elif dest.read_bytes() != fixture.read_bytes():
                problems.append("v%d: differs tests/fixtures/partner_list.prpt" % n)
    return problems


if __name__ == "__main__":
    drift = find_drift()
    for line in drift:
        print(line)
    print("OK: all native copies identical to engine/native" if not drift else "DRIFT: %d problem(s)" % len(drift))
    sys.exit(1 if drift else 0)
```

- [ ] **Step 5: Write the drift pytest `engine/native/tests/test_no_drift.py`**

```python
"""Every vNN/pentaho_reports/native must be a byte-identical copy of engine/native.
Skips when not running inside the repo (e.g. a copied-out module)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()


def _repo_root():
    for parent in HERE.parents:
        if (parent / "tools" / "check_drift.py").exists() and (parent / "engine" / "native").is_dir():
            return parent
    return None


def test_native_copies_do_not_drift():
    repo = _repo_root()
    if repo is None:
        pytest.skip("not inside the pentaho_odoo_workbench repo")
    sys.path.insert(0, str(repo / "tools"))
    import check_drift  # noqa: E402
    assert check_drift.find_drift(repo) == []
```

- [ ] **Step 6: Run sync, then drift; expect clean**

```bash
python3 tools/sync_native.py && python3 tools/check_drift.py
```
Expected: `synced v19/pentaho_reports/native` then `OK: all native copies identical to engine/native`.

- [ ] **Step 7: Prove drift is detected**

```bash
echo "# drift" >> v19/pentaho_reports/native/fonts.py; python3 tools/check_drift.py; echo "exit=$?"; python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py
```
Expected: first run prints `v19: differs native/fonts.py` and `exit=1`; second run prints OK.

- [ ] **Step 8: Run the engine test suite from its new home (baseline — fixture errors are expected until Task 2)**

```bash
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q 2>&1 | tail -3; cd ../../..
```
Expected: `14 failed, 70 passed, 7 skipped, 12 errors` (all failures/errors are `FileNotFoundError` for fixtures) and `test_no_drift.py` passes.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "Restructure: v19/pentaho_reports, canonical engine/native, sync + drift tools

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 2: Vendor credential-scrubbed fixtures and make the engine tests self-contained

**Files:**
- Create: `tools/scrub_fixture.py`, `fixtures/README.md`, `fixtures/*.prpt` (8 files), `engine/native/tests/test_fixtures_scrubbed.py`
- Modify: `engine/native/tests/conftest.py` (rewrite), `engine/native/tests/test_date_field.py:9-26`, `engine/native/tests/test_preview_render.py:12-24`

**Interfaces:**
- Produces: `tools/scrub_fixture.py SRC DEST [--query SQL] [--label TEXT]` (CLI) and importable `scrub_fixture.scrub(src: Path, dest: Path, query: str = None, label: str = None) -> None`. Conftest constants (unchanged names): `DELIVERY_RECEIPT_PRPT, SALES_INVOICE_PRPT, AP_VOUCHER_PRPT, BIR_2307_PRPT, GL_LISTING_NESTED_PRPT, BARCODE_PRPT` plus new `EVERGOOD_SALE_REPORT_PRPT, PRINT_SUPPLIER_CHECK_PRPT, PARTNER_LIST_PRPT`, and `FIXTURES_DIR` (Path or None). Each constant is a `_FixturePath` whose `.read_bytes()` calls `pytest.skip(...)` when the file is absent.

Source files (outside the repo): `/Volumes/Workspace/Development/Workbench/pentaho-report-designer/sample_prpt/` — `piaggio_odoo_sh__delivery_receipt.prpt`, `piaggio_odoo_sh__sales_invoice.prpt`, `piaggio_odoo_sh__ap_voucher.prpt`, `piaggio_odoo_sh__BIR_2307.prpt`, `evergood_minimart__sale_report.prpt`, `amici_v11__gl_listing_hardcode_sample.prpt`, `amici_v11__print_supplier_check.prpt`, `frpic_v16__product_barcode.prpt`.

- [ ] **Step 1: Write the scrub test first (`engine/native/tests/test_fixtures_scrubbed.py`)**

```python
"""Vendored fixtures must not carry database credentials (sql-ds.xml connection block)."""
import re
import zipfile

import pytest

from conftest import FIXTURES_DIR

EXPECTED = {
    "delivery_receipt.prpt", "sales_invoice.prpt", "ap_voucher.prpt", "BIR_2307.prpt",
    "evergood_sale_report.prpt", "gl_listing_nested.prpt", "print_supplier_check.prpt",
    "product_barcode.prpt",
}


def _sql_ds_parts(path):
    with zipfile.ZipFile(str(path)) as zf:
        for name in zf.namelist():
            if name.endswith("sql-ds.xml"):
                yield name, zf.read(name).decode("utf-8", "replace")


def test_all_expected_fixtures_present():
    if FIXTURES_DIR is None:
        pytest.skip("fixtures dir not found")
    present = {p.name for p in FIXTURES_DIR.glob("*.prpt")}
    assert EXPECTED <= present, sorted(EXPECTED - present)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_has_no_credentials(name):
    if FIXTURES_DIR is None:
        pytest.skip("fixtures dir not found")
    parts = list(_sql_ds_parts(FIXTURES_DIR / name))
    assert parts, "fixture has no sql-ds.xml?"
    for part, xml in parts:
        assert "encrypted:" not in xml, part
        users = re.findall(r'<data:property name="user">([^<]*)</data:property>', xml)
        assert users and set(users) == {"demo"}, (part, users)
        passwords = re.findall(r'<data:property name="password">([^<]*)</data:property>', xml)
        assert set(passwords) <= {""}, (part, passwords)
        urls = re.findall(r"<data:url>([^<]*)</data:url>", xml)
        assert set(urls) <= {"jdbc:postgresql://localhost/demo"}, (part, urls)
        assert "::pentaho-reporting::hostname\">" not in xml or \
            re.search(r'name="::pentaho-reporting::hostname">localhost<', xml), part


def test_mimetype_is_first_and_stored():
    if FIXTURES_DIR is None:
        pytest.skip("fixtures dir not found")
    for name in sorted(EXPECTED):
        with zipfile.ZipFile(str(FIXTURES_DIR / name)) as zf:
            first = zf.infolist()[0]
            assert first.filename == "mimetype", name
            assert first.compress_type == zipfile.ZIP_STORED, name
```

- [ ] **Step 2: Rewrite `engine/native/tests/conftest.py`**

```python
"""Shared test wiring for the native engine.

* Puts the directory containing the `native` package on sys.path so tests
  import `native.*` whether they run from engine/native/tests (canonical)
  or from vNN/pentaho_reports/native/tests (synced copy).
* Locates the vendored .prpt fixtures: $PENTAHO_FIXTURES, else the nearest
  ancestor `fixtures/` dir containing delivery_receipt.prpt. When absent,
  fixture-backed tests SKIP (never FileNotFoundError).
"""
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PACKAGE_PARENT = HERE.parents[1]  # dir that contains the `native` package
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

MODULE_DIR = PACKAGE_PARENT  # kept for older imports


def _find_fixtures_dir():
    env = os.environ.get("PENTAHO_FIXTURES")
    if env:
        return Path(env)
    for parent in HERE.parents:
        candidate = parent / "fixtures"
        if (candidate / "delivery_receipt.prpt").exists():
            return candidate
    return None


FIXTURES_DIR = _find_fixtures_dir()


class _FixturePath(type(Path())):
    """A Path whose read_bytes() skips the current test when the file is absent."""

    def read_bytes(self):
        if not self.exists():
            pytest.skip("vendored .prpt fixture not available: %s "
                        "(set PENTAHO_FIXTURES or run inside the repo)" % self)
        return super().read_bytes()


def fixture_path(name):
    base = FIXTURES_DIR if FIXTURES_DIR is not None else Path("/nonexistent/pentaho-fixtures")
    return _FixturePath(base / name)


DELIVERY_RECEIPT_PRPT = fixture_path("delivery_receipt.prpt")
SALES_INVOICE_PRPT = fixture_path("sales_invoice.prpt")
AP_VOUCHER_PRPT = fixture_path("ap_voucher.prpt")
BIR_2307_PRPT = fixture_path("BIR_2307.prpt")
EVERGOOD_SALE_REPORT_PRPT = fixture_path("evergood_sale_report.prpt")
# real-world multi-level (nested group-body) sample: a GL listing grouped by
# account then sub-account
GL_LISTING_NESTED_PRPT = fixture_path("gl_listing_nested.prpt")
# has a <date-field format-string="MM/dd/yyyy"> and nothing else unsupported
PRINT_SUPPLIER_CHECK_PRPT = fixture_path("print_supplier_check.prpt")
# real-world code128 <sbarcodes:simple-barcodes> sample (product label sheet)
BARCODE_PRPT = fixture_path("product_barcode.prpt")
# synthetic: evergood_sale_report with its query re-pointed at res_partner
PARTNER_LIST_PRPT = fixture_path("partner_list.prpt")
```

- [ ] **Step 3: Update the two tests that built their own paths**

`engine/native/tests/test_date_field.py` — replace lines 9 and 20-26:
```python
from conftest import PRINT_SUPPLIER_CHECK_PRPT
```
```python
CHECK_VOUCHER_PRPT = PRINT_SUPPLIER_CHECK_PRPT
```
(delete the `pytestmark = pytest.mark.skipif(...)` block — `read_bytes()` now skips by itself; keep the explanatory comment above the constant).

`engine/native/tests/test_preview_render.py` — replace line 12 with `from conftest import EVERGOOD_SALE_REPORT_PRPT`, line 19 with `SALE_REPORT_PRPT = EVERGOOD_SALE_REPORT_PRPT`, and delete the `pytestmark = pytest.mark.skipif(...)` block (lines 21-24).

- [ ] **Step 4: Run the suite — expect the fixture tests to SKIP (not error) and the scrub tests to skip**

```bash
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q 2>&1 | tail -3; cd ../../..
```
Expected: `0 failed`, `0 errors`, skips ≈ 40+ (every fixture-backed test), passes for the pure tests.

- [ ] **Step 5: Write `tools/scrub_fixture.py`**

```python
#!/usr/bin/env python3
"""Copy a .prpt while scrubbing its embedded JDBC connection details.

Every sql-ds.xml part (root and nested sub-reports) gets:
  user -> demo, password -> "", url -> jdbc:postgresql://localhost/demo,
  ::pentaho-reporting::hostname -> localhost, ::pentaho-reporting::name /
  ::pentaho-reporting::database-name -> demo.
Optionally rewrites the first <data:static-query> (--query) and the first
<core:value> label in layout.xml (--label) — used to derive synthetic fixtures.
All other parts are copied byte-for-byte; `mimetype` stays first and STORED.
"""
import argparse
import re
import zipfile
from pathlib import Path

_REPLACEMENTS = [
    (re.compile(r'(<data:property name="user">)[^<]*(</data:property>)'), r"\1demo\2"),
    (re.compile(r'(<data:property name="password">)[^<]*(</data:property>)'), r"\1\2"),
    (re.compile(r"(<data:url>)[^<]*(</data:url>)"), r"\1jdbc:postgresql://localhost/demo\2"),
    (re.compile(r'(<data:property name="::pentaho-reporting::hostname">)[^<]*(</data:property>)'), r"\1localhost\2"),
    (re.compile(r'(<data:property name="::pentaho-reporting::name">)[^<]*(</data:property>)'), r"\1demo\2"),
    (re.compile(r'(<data:property name="::pentaho-reporting::database-name">)[^<]*(</data:property>)'), r"\1demo\2"),
]


def _scrub_sql_ds(xml: str, query: str = None) -> str:
    for pattern, repl in _REPLACEMENTS:
        xml = pattern.sub(repl, xml)
    if query is not None:
        xml = re.sub(r"(<data:static-query>)(.*?)(</data:static-query>)",
                     lambda m: m.group(1) + _xml_escape(query) + m.group(3), xml, count=1, flags=re.S)
    return xml


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def scrub(src: Path, dest: Path, query: str = None, label: str = None) -> None:
    with zipfile.ZipFile(str(src)) as zin:
        infos = zin.infolist()
        parts = [(info, zin.read(info.filename)) for info in infos]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(dest), "w") as zout:
        for info, data in parts:
            name = info.filename
            if name.endswith("sql-ds.xml"):
                # only the ROOT sql-ds.xml gets the query rewrite; nested ones are scrubbed only
                data = _scrub_sql_ds(data.decode("utf-8"), query if name == "datasources/sql-ds.xml" else None).encode("utf-8")
            elif name == "layout.xml" and label is not None:
                data = re.sub(r"(<core:value>)[^<]*(</core:value>)", r"\g<1>%s\g<2>" % _xml_escape(label),
                              data.decode("utf-8"), count=1).encode("utf-8")
            out = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            out.compress_type = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            out.external_attr = info.external_attr
            zout.writestr(out, data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("dest", type=Path)
    ap.add_argument("--query", help="replace the root static-query SQL")
    ap.add_argument("--label", help="replace the first <core:value> label in layout.xml")
    args = ap.parse_args()
    scrub(args.src, args.dest, query=args.query, label=args.label)
    print("wrote", args.dest)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Vendor the eight fixtures**

```bash
S=/Volumes/Workspace/Development/Workbench/pentaho-report-designer/sample_prpt
python3 tools/scrub_fixture.py $S/piaggio_odoo_sh__delivery_receipt.prpt   fixtures/delivery_receipt.prpt
python3 tools/scrub_fixture.py $S/piaggio_odoo_sh__sales_invoice.prpt      fixtures/sales_invoice.prpt
python3 tools/scrub_fixture.py $S/piaggio_odoo_sh__ap_voucher.prpt         fixtures/ap_voucher.prpt
python3 tools/scrub_fixture.py $S/piaggio_odoo_sh__BIR_2307.prpt           fixtures/BIR_2307.prpt
python3 tools/scrub_fixture.py $S/evergood_minimart__sale_report.prpt      fixtures/evergood_sale_report.prpt
python3 tools/scrub_fixture.py $S/amici_v11__gl_listing_hardcode_sample.prpt fixtures/gl_listing_nested.prpt
python3 tools/scrub_fixture.py $S/amici_v11__print_supplier_check.prpt     fixtures/print_supplier_check.prpt
python3 tools/scrub_fixture.py $S/frpic_v16__product_barcode.prpt          fixtures/product_barcode.prpt
du -ch fixtures/*.prpt | tail -1
```
Expected: eight files, total < 300 KB.

- [ ] **Step 7: Write `fixtures/README.md`**

```markdown
# Test fixtures

Real-world `.prpt` reports used by the engine tests (`engine/native/tests`). Each was
copied with `tools/scrub_fixture.py`, which replaces the JDBC connection details the
Pentaho Report Designer embeds in `datasources/sql-ds.xml` (user → `demo`, password →
empty, url → `jdbc:postgresql://localhost/demo`). The renderer never reads those
properties — it runs the report's `static-query` on Odoo's own cursor.

| File | Exercises |
|---|---|
| `delivery_receipt.prpt`, `sales_invoice.prpt` | calibration layouts: bands, sub-report, group header/footer totals |
| `ap_voucher.prpt` | sub-report query executed once |
| `BIR_2307.prpt` | background image, custom 612×920 page |
| `evergood_sale_report.prpt` | minimal two-field detail band (preview-render path) |
| `gl_listing_nested.prpt` | nested `group-body` (multi-level groups) |
| `print_supplier_check.prpt` | `date-field` with a Java `SimpleDateFormat` mask |
| `product_barcode.prpt` | `code128` barcode element |
| `partner_list.prpt` | synthetic: `evergood_sale_report` re-pointed at `res_partner` — used by the Odoo module tests in every `vNN/pentaho_reports/tests/` |

`engine/native/tests/test_fixtures_scrubbed.py` fails if any fixture carries credentials.
```

- [ ] **Step 8: Run the full engine suite — everything fixture-backed now runs**

```bash
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q 2>&1 | tail -3; cd ../../..
```
Expected: `0 failed`, `0 errors`; skipped count drops to the 7 pre-existing skips (+1 for `partner_list.prpt`, created in Task 5). Scrub tests pass.

- [ ] **Step 9: Sync, drift, commit**

```bash
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && git add -A && git commit -m "Vendor credential-scrubbed .prpt fixtures; engine tests self-contained

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 3: Port the engine to the Python 3.6 floor

**Files:**
- Modify: `engine/native/model.py` (dataclasses → plain classes), `engine/native/{bundle,fonts,formats,query,renderer,painter}.py` (remove `from __future__ import annotations`; convert annotations)
- Create: `engine/native/COMPAT.md`

**Interfaces:**
- Produces: identical public API. Model classes keep the same constructor keyword arguments, attribute names, defaults, and field-wise equality (`Style() == Style()` is True; `Element(kind="label") != Element(kind="band")`).

The exact lines that currently use 3.7+/3.10-style annotations (verified by grep):
`bundle.py:69,73,102,103,104,313,371,380,423` · `fonts.py:54,79` · `query.py:9,18` · `formats.py:65,108,139` · `renderer.py:35(docstring only, leave),63,79,95,114,118,298` · `painter.py:25,89,92,118,190` · all of `model.py`.

Conversion rules: `X | None` → `Optional[X]`; `list[T]` → `List[T]`; `dict[K, V]` → `Dict[K, V]`; `tuple[A, B]` → `Tuple[A, B]`; `list[list[dict]]` → `List[List[dict]]`; forward references stay quoted strings (`"PrptBundle"`, `"Group"`, `"_Flow"`). Add `from typing import Dict, List, Optional, Tuple` (only the names used) to each file. Delete the `from __future__ import annotations` line in all seven files.

- [ ] **Step 1: Create the py3.6 scratch venv (reportlab pin = Odoo 11's)**

```bash
V=/private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/venvs
mkdir -p $V && /Library/Frameworks/Python.framework/Versions/3.6/bin/python3 -m venv $V/py36-rl3559
$V/py36-rl3559/bin/python -m pip install -q --upgrade "pip<22" && $V/py36-rl3559/bin/python -m pip install -q "reportlab==3.5.59" "Pillow<9" "pytest<7.1" "pypdf<4"
$V/py36-rl3559/bin/python -c "import reportlab, pypdf, pytest, PIL; print(reportlab.Version)"
```
Expected: `3.5.59`. (If pip cannot fetch cp36 wheels, add `--only-binary=:all:`; report the exact error rather than improvising other pins.)

- [ ] **Step 2: Prove the current engine FAILS on 3.6**

```bash
$V/py36-rl3559/bin/python -c "import sys; sys.path.insert(0,'engine'); import native.renderer" 2>&1 | tail -1
```
Expected: `SyntaxError: future feature annotations is not defined` (or an `ImportError: No module named 'dataclasses'`).

- [ ] **Step 3: Rewrite `engine/native/model.py` — replace the `dataclasses` import and all seven classes**

Replace `from dataclasses import dataclass, field as dc_field` with `from typing import Dict, List, Optional, Tuple` and add this base class right after `UnsupportedFeature`:

```python
class _Record(object):
    """Minimal stand-in for @dataclass (the engine must import on Python 3.6):
    keyword constructor with per-instance defaults, field-wise equality, repr.

    Subclasses list their fields in `_fields` as (name, default_or_factory,
    is_factory) tuples; `_required` names fields without a default.
    """
    _fields = ()  # type: Tuple[Tuple[str, object, bool], ...]
    _required = ()  # type: Tuple[str, ...]

    def __init__(self, *args, **kwargs):
        names = [f[0] for f in self._fields]
        if len(args) > len(names):
            raise TypeError("%s() takes at most %d positional arguments" % (type(self).__name__, len(names)))
        for name, value in zip(names, args):
            if name in kwargs:
                raise TypeError("%s() got multiple values for argument %r" % (type(self).__name__, name))
            kwargs[name] = value
        unknown = set(kwargs) - set(names)
        if unknown:
            raise TypeError("%s() got unexpected keyword argument(s): %s" % (type(self).__name__, ", ".join(sorted(unknown))))
        for name, default, is_factory in self._fields:
            if name in kwargs:
                value = kwargs[name]
            elif name in self._required:
                raise TypeError("%s() missing required argument: %r" % (type(self).__name__, name))
            else:
                value = default() if is_factory else default
            setattr(self, name, value)

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return all(getattr(self, f[0]) == getattr(other, f[0]) for f in self._fields)

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    __hash__ = None  # mutable, like an eq=True dataclass

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__,
                           ", ".join("%s=%r" % (f[0], getattr(self, f[0])) for f in self._fields))
```

Then the seven classes become (keep every existing comment next to its field):

```python
class BorderSide(_Record):
    _fields = (("width", None, False), ("style", None, False))
    _required = ("width", "style")   # style: 'solid', 'dashed', ... (only drawable sides are stored)


class Style(_Record):
    _fields = (
        ("x", 0.0, False), ("y", 0.0, False), ("width", 0.0, False), ("height", 0.0, False),
        ("height_pct", None, False),      # min-height="100%" → 100.0
        ("font_face", None, False), ("font_size", None, False),
        ("bold", False, False), ("italic", False, False), ("underline", False, False),
        ("align", None, False),           # left | center | right
        ("valign", None, False),          # top | middle | bottom
        ("borders", dict, True),          # Dict[str, BorderSide]
        ("padding", dict, True),          # Dict[str, float]
        ("dynamic_height", False, False), ("scale", False, False), ("keep_aspect", False, False),
        ("draw_shape", False, False),
        ("bg_color", None, False),        # raw color string, e.g. "#c9c98b" or "light_gray"
    )


class Element(_Record):
    _fields = (
        ("kind", None, False),            # label | text-field | number-field | content |
        #                                   content-field | band | horizontal-line | sub-report
        ("style", Style, True),
        ("field", None, False),           # data binding
        ("value", None, False),           # label text
        ("fmt", None, False),             # explicit format-string, if any
        ("barcode_type", None, False),    # kind == simple-barcodes/simple-barcode, e.g. "code128"
        ("elements", list, True),         # kind == band  (List[Element])
        ("subreport", None, False),       # kind == sub-report
        ("resource", None, False),        # kind == content (bytes)
    )
    _required = ("kind",)


class Band(_Record):
    _fields = (("elements", list, True), ("style", Style, True))


class Group(_Record):
    _fields = (
        ("fields", list, True),
        ("header", Band, True), ("footer", Band, True), ("details", Band, True), ("no_data", Band, True),
        # a group parsed from a <group-body> sets `child` (the nested <group>) and
        # leaves details/no_data empty; a group parsed from a <data-body> is a LEAF
        # (has details/no_data, child is None). Single-level reports never set
        # this, so they keep working unchanged.
        ("child", None, False),
    )
```

`PageDef` keeps its `size_pt` property unchanged:

```python
class PageDef(_Record):
    _fields = (
        ("format", "LETTER", False),
        ("orientation", "portrait", False),
        ("margins", (0.0, 0.0, 0.0, 0.0), False),   # top,left,bottom,right
        ("width", 0.0, False),    # explicit page size (custom formats, e.g. BIR 612x920);
        ("height", 0.0, False),   # takes precedence over the named format
    )

    @property
    def size_pt(self):
        # type: () -> Tuple[float, float]
        ...  # body unchanged
```

```python
class PlainParameter(_Record):
    _fields = (
        ("name", None, False),
        ("mandatory", False, False),
        ("ptype", "java.lang.Object", False),
        ("attrs", dict, True),            # Dict[str, str]
    )
    _required = ("name",)
```

- [ ] **Step 4: Convert the other six files**

For each of `bundle.py fonts.py formats.py query.py renderer.py painter.py`: delete `from __future__ import annotations`; add the needed `from typing import …` after the stdlib imports; apply the conversion rules to the listed lines. Examples of the resulting lines:

```python
# bundle.py
def _attrs_by_local(node) -> Dict[str, str]:
def _to_float(value: Optional[str], default: float = 0.0) -> float:
        self.query_name = None   # type: Optional[str]
        self.sql = None          # type: Optional[str]
        self.parameters = {}     # type: Dict[str, PlainParameter]
    def _load_resource(self, value: Optional[str]) -> bytes:
    def _apply_bg_color(a: Dict[str, str], style: Style) -> None:
    def _parse_borders(a: Dict[str, str], style: Style) -> None:
    def _find_sql_query(self, query_name: str) -> Optional[str]:
# fonts.py
_arial_family = None  # type: Optional[dict]
def resolve(face: Optional[str], bold: bool = False, italic: bool = False) -> str:
# formats.py
def format_number(value, pattern: Optional[str]) -> str:
def java_dateformat_to_strftime(pattern: str) -> Optional[str]:
def format_value(value, pattern: Optional[str]) -> str:
# query.py
def prepare_sql(sql: str, parameters: dict) -> Tuple[str, list]:
    pieces = []  # type: List[str]
# renderer.py
    def _fetch_rows(self, bundle: PrptBundle, parameters: dict) -> List[dict]:
    def _emit_report(self, flow: "_Flow", bundle: PrptBundle, rows: List[dict], parameters: dict) -> None:
    def _emit_group(self, flow: "_Flow", group: Group, rows: List[dict], subrenderer) -> None:
    def _partition_rows(rows: List[dict], fields: List[str]) -> List[List[dict]]:
        groups = []  # type: List[List[dict]]
        self.cursor = None  # type: Optional[float]  — None → page not started yet
# painter.py
def parse_color(value: Optional[str]) -> Optional[Tuple[float, float, float]]:
def wrap_text(text: str, font: str, size: float, width: float) -> List[str]:
    lines = []  # type: List[str]
def _insets(style: Style) -> Dict[str, float]:
    def _font(self, style: Style) -> Tuple[str, float]:
```
(Local variable annotations such as `pieces: list[str] = []` become type comments because PEP 526 local annotations are legal on 3.6 but `list[str]` is not evaluable — the comment form sidesteps both.)

- [ ] **Step 5: Verify on 3.6 — compile, import, full suite**

```bash
$V/py36-rl3559/bin/python -m compileall -q engine/native && echo COMPILE_OK
$V/py36-rl3559/bin/python -c "import sys; sys.path.insert(0,'engine'); import native.renderer, native.bundle; print('IMPORT_OK')"
cd engine/native/tests && $V/py36-rl3559/bin/python -m pytest -q 2>&1 | tail -3; cd ../../..
```
Expected: `COMPILE_OK`, `IMPORT_OK`, pytest `0 failed 0 errors`.

- [ ] **Step 6: Verify nothing regressed on 3.12 (odoo19 venv, reportlab 4.1)**

```bash
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q 2>&1 | tail -3; cd ../../..
grep -rn "from __future__\|dataclass\|| None\|list\[\|dict\[\|tuple\[" engine/native/*.py | grep -v "^\S*:\s*#" || echo "NO_MODERN_SYNTAX_LEFT"
```
Expected: same pass count as before; `NO_MODERN_SYNTAX_LEFT`.

- [ ] **Step 7: Write `engine/native/COMPAT.md`**

```markdown
# Compatibility rule for `engine/native`

This package is copied verbatim into `v11/…/v19/pentaho_reports/native`. The oldest
target, Odoo 11, runs on **Python 3.6.8**, so everything here must import and run on 3.6:

- no `dataclasses`, no `from __future__ import annotations`, no `X | None`,
  no `list[str]` / `dict[str, int]` / `tuple[...]` in evaluated annotations
  (use `typing.Optional/List/Dict/Tuple`, or a `# type:` comment for locals),
- no walrus (`:=`), no positional-only parameters, no `str.removeprefix`,
  no `functools.cached_property`, no `math.prod/dist`, no `zoneinfo`.
- f-strings are fine (3.6).
- reportlab: stay on the API slice used today (`pdfgen.canvas`, `pdfbase.pdfmetrics`,
  `pdfbase.ttfonts.TTFont`, `lib.colors`, `lib.utils.ImageReader`,
  `graphics.barcode.createBarcodeDrawing`); it is exercised against reportlab 3.5 → 5.0
  by `tools/engine_matrix.sh`.

Enforced by `tools/test_matrix.sh` (compileall with each Odoo's venv + the scratch matrix).
Python 3.5 (the `odoo:11` Docker image) is deliberately **not** supported.
```

- [ ] **Step 8: Sync, drift, commit**

```bash
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && git add -A && git commit -m "engine: Python 3.6 floor (plain classes instead of dataclasses, typing annotations)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 4: `tools/engine_matrix.sh` — engine tests across interpreter × reportlab pins

**Files:**
- Create: `tools/engine_matrix.sh`

**Interfaces:**
- Produces: `tools/engine_matrix.sh` (no args; exit 0 only if every combination passes; prints a table). Env override `SCRATCH_VENVS=<dir>` (default: the session scratchpad `venvs/` dir).

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Run the engine's pytest suite under every (Python, reportlab) pair the nine Odoo venvs ship.
# Scratch venvs are created on first use and reused afterwards.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH_VENVS:-/private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/venvs}"
mkdir -p "$SCRATCH"

# label | interpreter | reportlab pin | extra pins
COMBOS=(
  "py36-rl3559|/Library/Frameworks/Python.framework/Versions/3.6/bin/python3|3.5.59|Pillow<9 pytest<7.1 pypdf<4 pip<22"
  "py39-rl3559|/opt/homebrew/bin/python3.9|3.5.59|Pillow pytest pypdf"
  "py39-rl4410|/opt/homebrew/bin/python3.9|4.4.10|Pillow pytest pypdf"
  "py39-rl500|/opt/homebrew/bin/python3.9|5.0.0|Pillow pytest pypdf"
  "py310-rl368|/opt/homebrew/bin/python3.10|3.6.8|Pillow pytest pypdf"
  "py312-rl410|/opt/homebrew/bin/python3.12|4.1.0|Pillow pytest pypdf"
)

results=()
fail=0
for combo in "${COMBOS[@]}"; do
  IFS='|' read -r label py pin extras <<<"$combo"
  venv="$SCRATCH/$label"
  if [ ! -x "$venv/bin/python" ]; then
    echo "== creating $label ($py, reportlab==$pin)"
    "$py" -m venv "$venv" || { results+=("$label|VENV-FAIL"); fail=1; continue; }
    # shellcheck disable=SC2086
    "$venv/bin/python" -m pip install -q --upgrade pip $extras "reportlab==$pin" \
      || { results+=("$label|PIP-FAIL"); fail=1; continue; }
  fi
  rl="$("$venv/bin/python" -c 'import reportlab; print(reportlab.Version)' 2>/dev/null)"
  echo "== $label: python $("$venv/bin/python" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') reportlab $rl"
  if (cd "$REPO/engine/native/tests" && "$venv/bin/python" -m pytest -q -p no:cacheprovider 2>&1 | tail -1 | tee "$SCRATCH/$label.last"); then :; fi
  last="$(cat "$SCRATCH/$label.last")"
  if echo "$last" | grep -qE "(^| )(failed|error)"; then results+=("$label|FAIL|$last"); fail=1; else results+=("$label|PASS|$last"); fi
done

echo; echo "engine matrix:"
for r in "${results[@]}"; do echo "  $r"; done
exit $fail
```

- [ ] **Step 2: Make executable and run**

```bash
chmod +x tools/engine_matrix.sh && tools/engine_matrix.sh 2>&1 | tail -12
```
Expected: six lines all `PASS` (pytest summary `N passed, M skipped`). If a reportlab pin refuses to install on a given Python (e.g. no wheel), record the exact pip error in the task report — do **not** silently change the pin.

- [ ] **Step 3: Commit**

```bash
git add tools/engine_matrix.sh && git commit -m "tools: engine test matrix across Python × reportlab pins

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 5: The `partner_list.prpt` fixture (Odoo-independent, renders against `res_partner`)

**Files:**
- Create: `fixtures/partner_list.prpt` (generated), `engine/native/tests/test_partner_list.py`

**Interfaces:**
- Produces: `fixtures/partner_list.prpt` — derived from `fixtures/evergood_sale_report.prpt`; root query `select rp.id as so_no, rp.name as partner from res_partner rp where rp.id in (${ids}) order by rp.id`, title label `Partner List`. Layout fields stay `so_no` / `partner`. Synced into every `vNN/pentaho_reports/tests/fixtures/partner_list.prpt` by Task 1's sync script.

- [ ] **Step 1: Write the failing engine test**

```python
"""partner_list.prpt: the synthetic fixture the Odoo module tests install and render.
It must parse, reference only `res_partner`, and render stub rows to a PDF."""
from conftest import PARTNER_LIST_PRPT

from native.bundle import PrptBundle
from native.renderer import NativeRenderer


def test_partner_list_query_targets_res_partner_only():
    bundle = PrptBundle.from_bytes(PARTNER_LIST_PRPT.read_bytes())
    sql = bundle.sql.lower()
    assert "from res_partner" in sql
    assert "sale_order" not in sql
    assert "${ids}" in bundle.sql


def test_partner_list_renders_pdf_with_stub_rows():
    calls = []

    def execute_query(sql, params):
        calls.append((sql, params))
        return [{"so_no": 1, "partner": "Azure Interior"}, {"so_no": 2, "partner": "Deco Addict"}]

    out = NativeRenderer(execute_query).render(PARTNER_LIST_PRPT.read_bytes(), {"ids": [1, 2]}, "pdf")
    assert out.startswith(b"%PDF")
    assert len(calls) == 1
    assert "res_partner" in calls[0][0]
```

- [ ] **Step 2: Run it — expect SKIP (fixture absent)**

```bash
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q test_partner_list.py 2>&1 | tail -2; cd ../../..
```
Expected: `2 skipped`.

- [ ] **Step 3: Generate the fixture**

```bash
python3 tools/scrub_fixture.py fixtures/evergood_sale_report.prpt fixtures/partner_list.prpt \
  --query 'select rp.id as so_no, rp.name as partner from res_partner rp where rp.id in (${ids}) order by rp.id' \
  --label 'Partner List'
python3 - <<'PY'
import zipfile; z=zipfile.ZipFile("fixtures/partner_list.prpt")
print(z.read("datasources/sql-ds.xml").decode().split("<data:static-query>")[1].split("</data:static-query>")[0])
print("Partner List" in z.read("layout.xml").decode())
PY
```
Expected: the new query printed (note `${ids}` intact — the tool XML-escapes only `& < >`), then `True`.

- [ ] **Step 4: Run the test — expect PASS; sync; drift**

```bash
cd engine/native/tests && /Volumes/Workspace/Development/OdooWorkbench/odoo19/venv/bin/python -m pytest -q test_partner_list.py test_fixtures_scrubbed.py 2>&1 | tail -2; cd ../../..
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && ls v19/pentaho_reports/tests/fixtures/
```
Expected: all pass; `partner_list.prpt` present under `v19/pentaho_reports/tests/fixtures/`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "fixtures: synthetic partner_list.prpt for the Odoo module tests

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 6: v19 — reference modern module, universal tests, and the per-Odoo install harness

**Files:**
- Modify: `v19/pentaho_reports/__manifest__.py`, `v19/pentaho_reports/models/ir_actions_report.py`, `v19/pentaho_reports/controllers/main.py:18`
- Replace: `v19/pentaho_reports/tests/__init__.py`, delete `tests/test_native_rendering.py` and `tests/test_preview_controller.py`; create `tests/test_render.py`, `tests/test_controllers.py`
- Create: `v19/pentaho_reports/README.md`, `tools/odoo_install_test.sh`

**Interfaces:**
- Produces (Python, all versions will share these names):
  - `IrActionsReport._pentaho_prpt_content(self) -> bytes` (unchanged)
  - `IrActionsReport._pentaho_parameters(self, res_ids, data) -> dict` (unchanged)
  - `IrActionsReport._render_pentaho_report(self, res_ids, data=None) -> (bytes, str)` — **new**, `ensure_one`, the single place that calls `NativeRenderer`.
  - v16+ dispatch: `@api.model _render_pentaho(self, report_ref, res_ids, data=None) -> (bytes, str)` resolving `self._get_report(report_ref)`.
  - `@api.model render_report(self, report_id, res_ids=None, data=None) -> (content_b64: str, output_type: str, filename: str, direct_print: bool)` — JS entry point (unchanged contract).
- Produces (tests): `tests/test_render.py::TestPentahoRender`, `tests/test_controllers.py::TestPentahoControllers` — **version-agnostic** files (they feature-detect `group_ids` vs `groups_id`, `tagged`, the JSON route) so later tasks copy them unchanged.
- Produces (tool): `tools/odoo_install_test.sh NN` → exit 0 when Odoo NN installs the module into a fresh DB and all `pentaho_reports` tests pass; prints `RESULT vNN PASS|FAIL`; always drops the DB.

- [ ] **Step 1: Manifest**

Edit `v19/pentaho_reports/__manifest__.py`: keep everything, change/add:
```python
    'version': '19.0.2.0.0',
    'external_dependencies': {'python': ['reportlab']},
```
and append to the description's `Dependencies` section the line `- Python >= 3.6 (the renderer is shared, byte-identical, with the Odoo 11-19 builds of this module)`.

- [ ] **Step 2: Controller — Odoo 19 canonical JSON route type**

`v19/pentaho_reports/controllers/main.py:18`: `@http.route('/pentaho/preview', type='json', auth='user')` → `@http.route('/pentaho/preview', type='jsonrpc', auth='user')`.

- [ ] **Step 3: Model — factor the render core + add the 16+ dispatch hook**

In `v19/pentaho_reports/models/ir_actions_report.py` replace the whole `# ── rendering` section (from `def _pentaho_parameters` to the end of file) with:

```python
    # ── rendering ───────────────────────────────────────────

    def _pentaho_parameters(self, res_ids, data):
        """Reserved parameters + the caller's variables, as the .prpt sees them."""
        variables = (data or {}).get('variables') or {}
        ids = res_ids or variables.get('ids') or self.env.context.get('active_ids') or []
        if isinstance(ids, int):
            ids = [ids]
        parameters = {
            'ids': list(ids),
            'user_id': self.env.uid,
            'user_name': self.env.user.name,
            'context_lang': self.env.context.get('lang', 'en_US'),
            'context_tz': self.env.context.get('tz', 'UTC'),
        }
        parameters.update(variables)
        return parameters

    def _render_pentaho_report(self, res_ids, data=None):
        """Render this .prpt report in-process → (report_bytes, output_type).

        The one place the native engine is invoked; both the JS entry point
        (render_report) and Odoo's generic report dispatch (_render_pentaho)
        funnel through here.
        """
        self.ensure_one()
        if self.report_type != 'pentaho':
            raise UserError(_('Report %s is not a Pentaho report') % self.report_name)

        def execute_query(sql, params):
            # savepoint so a bad query cannot poison the surrounding transaction
            with self.env.cr.savepoint():
                self.env.cr.execute(sql, params)
                return self.env.cr.dictfetchall()

        output_type = ((data or {}).get('output_type')
                       or self.pentaho_report_output_type or 'pdf')
        try:
            rendered = NativeRenderer(execute_query).render(
                self._pentaho_prpt_content(),
                self._pentaho_parameters(res_ids, data),
                output_type)
        except UnsupportedFeature as e:
            raise UserError(
                _('The Pentaho renderer cannot render this report: %s') % e)
        _logger.info('Pentaho renderer produced %d bytes (%s) for %s',
                     len(rendered), output_type, self.report_name)
        return rendered, output_type

    @api.model
    def _render_pentaho(self, report_ref, res_ids, data=None):
        """Odoo >= 16 generic dispatch: ir.actions.report._render() calls
        _render_<report_type>(report_ref, res_ids, data)."""
        report = self._get_report(report_ref)
        return report._render_pentaho_report(res_ids, data)

    @api.model
    def render_report(self, report_id, res_ids=None, data=None):
        """UI entry point → (content_b64, output_type, filename, direct_print).

        Called over ORM by the JS action handler with the report id, the
        active record ids, and the action's ``data`` dict.
        """
        report = self.browse(report_id).exists()
        if not report or report.report_type != 'pentaho':
            raise UserError(_('Report %s is not a Pentaho report') % report_id)
        content, output_type = report._render_pentaho_report(res_ids or [], data)

        filename = report.report_name
        custom = ((data or {}).get('variables') or {}).get('filename')
        if custom:
            # extension is re-added from output_type by the download controller
            filename = custom.rsplit('.', 1)[0] if '.' in custom else custom

        return (base64.b64encode(content).decode(), output_type,
                filename, report.pentaho_direct_print)
```
(The old `_render_pentaho(self, report_id, res_ids, data=None)` is gone; `render_report` no longer calls it.)

- [ ] **Step 4: Universal module tests — `tests/test_render.py`**

```python
# -*- coding: utf-8 -*-
"""In-process rendering through ir.actions.report — self-contained: installs its
own report record bound to res.partner with the partner_list.prpt fixture.

Version-agnostic: runs unchanged on Odoo 11 → 19 (see _tagged / _render_dispatch).
"""
import base64
import os

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

try:  # Odoo >= 12
    from odoo.tests import tagged
except ImportError:  # Odoo 11: no test tags, tests run at install
    def tagged(*tags):
        return lambda cls: cls

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'partner_list.prpt')


@tagged('post_install', '-at_install')
class TestPentahoRender(TransactionCase):

    def setUp(self):
        super(TestPentahoRender, self).setUp()
        with open(FIXTURE, 'rb') as f:
            self.prpt_b64 = base64.b64encode(f.read())
        self.Report = self.env['ir.actions.report']
        self.report = self.Report.create({
            'name': 'Pentaho Test Partner List',
            'report_name': 'pentaho_reports.test_partner_list',
            'model': 'res.partner',
            'report_type': 'pentaho',
            'pentaho_file': self.prpt_b64,
            'pentaho_filename': 'partner_list.prpt',
        })
        self.partners = self.env['res.partner'].search([], limit=3, order='id')
        self.assertTrue(self.partners, 'base always ships partners')

    def test_create_forces_action_type(self):
        self.assertEqual(self.report.type, 'ir.actions.report')
        self.assertEqual(self.report.pentaho_report_output_type, 'pdf')

    def test_render_report_returns_pdf_tuple(self):
        content_b64, output_type, filename, direct_print = self.Report.render_report(
            self.report.id, self.partners.ids, {})
        self.assertEqual(output_type, 'pdf')
        self.assertEqual(filename, 'pentaho_reports.test_partner_list')
        self.assertFalse(direct_print)
        self.assertTrue(base64.b64decode(content_b64).startswith(b'%PDF'))

    def test_render_report_custom_filename_strips_extension(self):
        _c, _t, filename, _d = self.Report.render_report(
            self.report.id, self.partners.ids, {'variables': {'filename': 'partners.pdf'}})
        self.assertEqual(filename, 'partners')

    def test_render_report_zero_rows_still_pdf(self):
        content_b64, _t, _f, _d = self.Report.render_report(self.report.id, [], {})
        self.assertTrue(base64.b64decode(content_b64).startswith(b'%PDF'))

    def test_render_report_rejects_non_pentaho_report(self):
        qweb = self.Report.search([('report_type', '=', 'qweb-pdf')], limit=1)
        if not qweb:
            self.skipTest('no qweb report in this database')
        with self.assertRaises(UserError):
            self.Report.render_report(qweb.id, self.partners.ids, {})

    def test_missing_file_raises_validation_error(self):
        from odoo.exceptions import ValidationError
        self.report.with_context(skip_load_file=True).write({'pentaho_file': False})
        with self.assertRaises(ValidationError):
            self.report._render_pentaho_report(self.partners.ids, {})

    def test_core_render_dispatch_finds_pentaho(self):
        """Odoo's generic render entry point must reach our renderer on every
        version: 11-13 `render()`, 14-15 `_render(res_ids)`, 16+ `_render(ref, res_ids)`."""
        Report = self.report
        if hasattr(Report, '_render') and 'report_ref' in Report._render.__code__.co_varnames:
            out = self.Report._render(Report.id, self.partners.ids)
        elif hasattr(Report, '_render'):
            out = Report._render(self.partners.ids)
        else:
            out = Report.render(self.partners.ids)
        self.assertIsNotNone(out, 'generic dispatch did not find the pentaho renderer')
        content, output_type = out
        self.assertEqual(output_type, 'pdf')
        self.assertTrue(content.startswith(b'%PDF'))
```

- [ ] **Step 5: Universal module tests — `tests/test_controllers.py`**

```python
# -*- coding: utf-8 -*-
"""HTTP layer: /pentaho/preview (JSON-RPC, gated to report authors),
/pentaho/download and /pentaho/print (PDF replay; fileToken cookie contract
that Odoo 11-14's session.get_file depends on).

Version-agnostic: posts JSON through the raw requests session (works on 11+),
feature-detects the res.users groups field name (group_ids on 19).
"""
import base64
import json
import os

import requests

import odoo
from odoo.tests.common import HttpCase

try:  # Odoo >= 12
    from odoo.tests import tagged
except ImportError:  # Odoo 11
    def tagged(*tags):
        return lambda cls: cls

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'partner_list.prpt')


@tagged('post_install', '-at_install')
class TestPentahoControllers(HttpCase):

    def setUp(self):
        super(TestPentahoControllers, self).setUp()
        with open(FIXTURE, 'rb') as f:
            self.prpt_b64 = base64.b64encode(f.read()).decode()
        self.partner_ids = self.env['res.partner'].search([], limit=2, order='id').ids

    # ── helpers ────────────────────────────────────────────────────────

    def _url(self, path):
        # http_port is the config key on every version (the CLI flag was --xmlrpc-port before 12)
        return 'http://127.0.0.1:%s%s' % (odoo.tools.config['http_port'], path)

    def _groups_field(self):
        return 'group_ids' if 'group_ids' in self.env['res.users']._fields else 'groups_id'

    def _make_user(self, login, *group_xmlids):
        vals = {
            'name': login, 'login': login, 'password': login,
            self._groups_field(): [(6, 0, [self.env.ref(x).id for x in group_xmlids])],
        }
        return self.env['res.users'].create(vals)

    def _raw_call(self, params):
        resp = self.opener.post(self._url('/pentaho/preview'), json={
            'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': params})
        return resp.json()

    def _call(self, params):
        body = self._raw_call(params)
        self.assertNotIn('error', body, body.get('error'))
        return body['result']

    def _preview_params(self):
        return {'prpt_b64': self.prpt_b64, 'model': 'res.partner', 'ids': self.partner_ids, 'variables': {}}

    # ── /pentaho/preview: positive ─────────────────────────────────────

    def test_preview_renders_pdf_for_admin(self):
        self.authenticate('admin', 'admin')
        result = self._call(self._preview_params())
        self.assertNotIn('error', result, result.get('error'))
        self.assertTrue(base64.b64decode(result['pdf_b64']).startswith(b'%PDF'))

    def test_preview_allows_report_author_without_admin(self):
        user = self._make_user('pentaho_author', 'base.group_user', 'base.group_system')
        self.assertFalse(user.share)
        self.authenticate('pentaho_author', 'pentaho_author')
        result = self._call(self._preview_params())
        self.assertTrue(base64.b64decode(result['pdf_b64']).startswith(b'%PDF'))

    # ── /pentaho/preview: the access gate ──────────────────────────────

    def _assert_access_error(self, body):
        self.assertIn('error', body, 'caller must not reach the render path')
        data = body['error'].get('data', {})
        self.assertIn('AccessError', '%s %s' % (data.get('name'), data.get('exception_type')))

    def test_preview_rejects_portal_user(self):
        user = self._make_user('pentaho_portal', 'base.group_portal')
        self.assertTrue(user.share)
        self.authenticate('pentaho_portal', 'pentaho_portal')
        self._assert_access_error(self._raw_call({'prpt_b64': 'eA==', 'model': False, 'ids': [], 'variables': {}}))

    def test_preview_rejects_internal_user_without_technical_access(self):
        user = self._make_user('pentaho_notech', 'base.group_user')
        self.assertFalse(user.share)
        self.authenticate('pentaho_notech', 'pentaho_notech')
        self._assert_access_error(self._raw_call({'prpt_b64': 'eA==', 'model': False, 'ids': [], 'variables': {}}))

    # ── /pentaho/preview: safe errors ──────────────────────────────────

    def test_preview_invalid_prpt_returns_safe_error(self):
        self.authenticate('admin', 'admin')
        result = self._call({'prpt_b64': base64.b64encode(b'not a real prpt').decode(),
                             'model': False, 'ids': [], 'variables': {}})
        self.assertIn('error', result)
        self.assertNotIn('Traceback', result['error'])
        self.assertNotIn('File "', result['error'])

    # ── /pentaho/download and /pentaho/print ───────────────────────────

    def _payload(self):
        return json.dumps([base64.b64encode(b'%PDF-1.4 fake').decode(), 'pdf', 'unit_test_report'])

    def test_download_replays_pdf_and_sets_file_token_cookie(self):
        self.authenticate('admin', 'admin')
        resp = self.opener.get(self._url('/pentaho/download'),
                               params={'data': self._payload(), 'token': '424242'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Content-Type'), 'application/pdf')
        self.assertIn('unit_test_report.pdf', resp.headers.get('Content-Disposition', ''))
        self.assertTrue(resp.content.startswith(b'%PDF'))
        self.assertEqual(resp.cookies.get('fileToken'), '424242',
                         'legacy session.get_file polls this cookie to unblock the UI')

    def test_print_returns_inline_pdf(self):
        self.authenticate('admin', 'admin')
        resp = self.opener.get(self._url('/pentaho/print'), params={'data': self._payload()})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Content-Type'), 'application/pdf')
        self.assertIn('inline', resp.headers.get('Content-Disposition', ''))

    def test_download_requires_login(self):
        anonymous = requests.Session()  # no session cookie at all
        resp = anonymous.get(self._url('/pentaho/download'),
                             params={'data': self._payload()}, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303, 401, 403, 404),
                      'auth="user" route must not serve anonymous callers')
```

`tests/__init__.py`:
```python
from . import test_render
from . import test_controllers
```
Delete `tests/test_native_rendering.py` and `tests/test_preview_controller.py`.

- [ ] **Step 6: `v19/pentaho_reports/README.md`**

```markdown
# pentaho_reports — Odoo 19

Pure-Python renderer for Pentaho `.prpt` reports (no Java, no Tomcat, works on Odoo.sh).
This folder is the Odoo **19** build; sibling folders `../v11` … `../v18` are the same module
for other versions. Requires Python ≥ 3.10 (Odoo 19's own floor) and reportlab (bundled with Odoo).

Install: copy this folder into your addons path (or `--addons-path=/path/to/v19`), then
`odoo-bin -d <db> -i pentaho_reports`. Settings → Technical → Reports → create a report with
type *Pentaho Report* and upload the `.prpt`.

Do not edit `native/` here — it is a synced copy of `../../engine/native` (see the root README).
```

- [ ] **Step 7: Write `tools/odoo_install_test.sh`**

```bash
#!/usr/bin/env bash
# Install vNN/pentaho_reports into a fresh throwaway DB on the local Odoo NN and run its tests.
# Usage: tools/odoo_install_test.sh 17      -> prints "RESULT v17 PASS" or "RESULT v17 FAIL", exit 0/1.
# Always drops the DB. Log kept at $LOGDIR/odoo_vNN.log.
set -u
N="${1:?odoo major version, e.g. 17}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WB=/Volumes/Workspace/Development/OdooWorkbench/odoo$N
PY="$WB/venv/bin/python"
ODOO_BIN="$WB/odoo/odoo-bin"
DB="pentaho_test_v$N"
PORT="180$N"
LOGDIR="${LOGDIR:-/private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/odoo-logs}"
mkdir -p "$LOGDIR"; LOG="$LOGDIR/odoo_v$N.log"

[ -x "$PY" ] || { echo "RESULT v$N FAIL (no venv python at $PY)"; exit 1; }
[ -f "$ODOO_BIN" ] || { echo "RESULT v$N FAIL (no odoo-bin at $ODOO_BIN)"; exit 1; }
[ -d "$REPO/v$N/pentaho_reports" ] || { echo "RESULT v$N FAIL (no v$N/pentaho_reports)"; exit 1; }

cleanup() { dropdb --if-exists "$DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
createdb -O "odoo$N" "$DB" || { echo "RESULT v$N FAIL (createdb)"; exit 1; }

TEST_TAGS=()
if [ "$N" -ge 12 ]; then TEST_TAGS=(--test-tags "/pentaho_reports"); fi
# Odoo 11-15 know --longpolling-port, 16+ --gevent-port (unknown options abort the run).
if [ "$N" -ge 16 ]; then LP_FLAG=(--gevent-port=$((PORT+1000))); else LP_FLAG=(--longpolling-port=$((PORT+1000))); fi

( cd "$WB/odoo" && "$PY" "$ODOO_BIN" \
    -d "$DB" -r "odoo$N" --db_host=localhost \
    --addons-path="$WB/odoo/addons,$REPO/v$N" \
    -i pentaho_reports --test-enable "${TEST_TAGS[@]}" \
    --stop-after-init --without-demo=all \
    --http-port="$PORT" "${LP_FLAG[@]}" \
    --log-level=test --logfile="$LOG" ) 2>>"$LOG"
rc=$?

ran=$(grep -cE "pentaho_reports.*(test_[a-z_]+|Starting|Ran [0-9]+ tests?)" "$LOG" || true)
bad=$(grep -E "(ERROR|CRITICAL) .*(pentaho_reports|odoo\.tests|odoo\.modules\.loading|odoo\.sql_db|Traceback)|FAIL: |ERROR: test_|^Traceback" "$LOG" | grep -v "test-tags" | head -20 || true)
echo "--- v$N: exit=$rc, test lines=$ran"
if [ $rc -ne 0 ] || [ -n "$bad" ] || [ "$ran" -eq 0 ]; then
  echo "$bad"; echo "RESULT v$N FAIL (see $LOG)"; exit 1
fi
echo "RESULT v$N PASS"
```

- [ ] **Step 8: Sync, run Odoo 19 end to end**

```bash
chmod +x tools/odoo_install_test.sh && python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && tools/odoo_install_test.sh 19; grep -E "Ran [0-9]+ tests|tests? (passed|failed)|test_[a-z_]+ .*(ok|FAIL|ERROR)|Module pentaho_reports: [0-9]+" /private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/odoo-logs/odoo_v19.log | tail -5
```
Expected: `RESULT v19 PASS`; the log shows all `TestPentahoRender` + `TestPentahoControllers` tests OK (Odoo 19 prints `N tests passed` / `0 failed`). If the run fails, read the log, fix the real cause (module code or the harness grep), re-run; do not weaken assertions to pass.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "v19: jsonrpc route, shared render core + _render_pentaho dispatch, universal tests, install harness

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 7: v18 and v17 (family C minus the `jsonrpc` route)

**Files:**
- Create: `v18/pentaho_reports/**`, `v17/pentaho_reports/**` (copies of v19 with the edits below)

**Interfaces:** identical to v19.

- [ ] **Step 1: Copy v19 twice and apply the version edits**

```bash
for N in 18 17; do
  rm -rf v$N && mkdir -p v$N && cp -R v19/pentaho_reports v$N/pentaho_reports
  find v$N -name __pycache__ -type d -prune -exec rm -rf {} +
  sed -i '' "s/'version': '19.0.2.0.0'/'version': '$N.0.2.0.0'/" v$N/pentaho_reports/__manifest__.py
  sed -i '' "s/@http.route('\/pentaho\/preview', type='jsonrpc', auth='user')/@http.route('\/pentaho\/preview', type='json', auth='user')/" v$N/pentaho_reports/controllers/main.py
  mv v$N/pentaho_reports/migrations/19.0.2.0.0 v$N/pentaho_reports/migrations/$N.0.2.0.0
  sed -i '' "s/# pentaho_reports — Odoo 19/# pentaho_reports — Odoo $N/; s/This folder is the Odoo \*\*19\*\* build; sibling folders \`..\/v11\` … \`..\/v18\`/This folder is the Odoo **$N** build; sibling folders \`..\/v11\` … \`..\/v19\`/; s/Requires Python ≥ 3.10 (Odoo 19's own floor)/Requires Python ≥ 3.10 (Odoo $N's own floor)/; s/--addons-path=\/path\/to\/v19/--addons-path=\/path\/to\/v$N/" v$N/pentaho_reports/README.md
  grep -n "'version'" v$N/pentaho_reports/__manifest__.py; grep -n "pentaho/preview" v$N/pentaho_reports/controllers/main.py; ls v$N/pentaho_reports/migrations
done
```
Expected per version: `'version': 'NN.0.2.0.0'`, `type='json'`, `migrations/NN.0.2.0.0`.

- [ ] **Step 2: Sync, drift, run both Odoos**

```bash
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && tools/odoo_install_test.sh 18 && tools/odoo_install_test.sh 17
```
Expected: `RESULT v18 PASS` and `RESULT v17 PASS`. Known difference to watch on 18: `res.users.groups_id` (the test's feature-detection handles it).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "v17, v18: same as v19 with type='json' preview route

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 8: v16 and v15 (family B: OWL registry + `attrs` views)

**Files:**
- Create: `v16/pentaho_reports/**`, `v15/pentaho_reports/**` from v17, then edit `views/report_views.xml` (both), `static/src/js/action_service.js` (both), `models/ir_actions_report.py` (v15 only)

**Interfaces:** identical to v19 except v15's dispatch hook is `_render_pentaho(self, res_ids, data=None)` (recordset).

- [ ] **Step 1: Copy and apply the mechanical edits**

```bash
for N in 16 15; do
  rm -rf v$N && mkdir -p v$N && cp -R v17/pentaho_reports v$N/pentaho_reports
  find v$N -name __pycache__ -type d -prune -exec rm -rf {} +
  sed -i '' "s/'version': '17.0.2.0.0'/'version': '$N.0.2.0.0'/" v$N/pentaho_reports/__manifest__.py
  mv v$N/pentaho_reports/migrations/17.0.2.0.0 v$N/pentaho_reports/migrations/$N.0.2.0.0
  sed -i '' "s/Odoo 17/Odoo $N/g; s/\*\*17\*\*/**$N**/; s/Python ≥ 3.10 (Odoo $N's own floor)/Python ≥ 3.7 (Odoo $N's own floor)/; s/\/v17/\/v$N/" v$N/pentaho_reports/README.md
done
```

- [ ] **Step 2: Views → `attrs` domains (both v16 and v15) — replace the whole `views/report_views.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Add Pentaho fields to report form -->
    <record id="act_report_xml_pentaho_view" model="ir.ui.view">
        <field name="name">ir.actions.report.pentaho</field>
        <field name="model">ir.actions.report</field>
        <field name="inherit_id" ref="base.act_report_xml_view"/>
        <field name="arch" type="xml">
            <field name="report_type" position="after">
                <field name="pentaho_report_output_type"
                       attrs="{'invisible': [('report_type', '!=', 'pentaho')], 'required': [('report_type', '=', 'pentaho')]}"/>
                <field name="pentaho_direct_print"
                       attrs="{'invisible': ['|', ('report_type', '!=', 'pentaho'), ('pentaho_report_output_type', '!=', 'pdf')]}"
                       help="Print the report directly in the browser without downloading. Only available for PDF reports."/>
                <field name="pentaho_file"
                       filename="pentaho_filename"
                       attrs="{'invisible': [('report_type', '!=', 'pentaho')], 'required': [('report_type', '=', 'pentaho'), ('pentaho_load_file', '=', False)]}"/>
                <field name="pentaho_filename" invisible="1"/>
                <field name="pentaho_load_file" attrs="{'invisible': [('report_type', '!=', 'pentaho')]}"/>
            </field>
        </field>
    </record>

    <!-- Search view filter for Pentaho reports -->
    <record id="act_report_xml_pentaho_search_view" model="ir.ui.view">
        <field name="name">ir.actions.report.search.pentaho</field>
        <field name="model">ir.actions.report</field>
        <field name="inherit_id" ref="base.act_report_xml_search_view"/>
        <field name="arch" type="xml">
            <search position="inside">
                <filter string="Pentaho Reports"
                        name="pentaho_reports"
                        domain="[('report_type', '=', 'pentaho')]"/>
            </search>
        </field>
    </record>
</odoo>
```

- [ ] **Step 3: JS — translation helper (both v16 and v15)**

In `static/src/js/action_service.js` remove the line `import { _t } from "@web/core/l10n/translation";` and, as the first statement inside `pentahoReportHandler` after the `if (action.report_type === "pentaho") {` line, add `const _t = env._t;`. (Odoo 15/16 expose `_t` on `env`; the `@web/core/l10n/translation` export of `_t` appears in 17.) Everything else in the handler is unchanged — `registry`, `download`, `env.services.{ui,orm,notification,action}` all exist in 15 and 16.

- [ ] **Step 4: v15 only — dispatch hook signature**

In `v15/pentaho_reports/models/ir_actions_report.py` replace the `_render_pentaho` method with:

```python
    def _render_pentaho(self, res_ids, data=None):
        """Odoo 14/15 generic dispatch: ir.actions.report._render(res_ids, data)
        calls _render_<report_type>(res_ids, data) on the report record."""
        return self._render_pentaho_report(res_ids, data)
```
(v16 keeps the `@api.model _render_pentaho(self, report_ref, res_ids, data=None)` form — 16 introduced `report_ref`.)

- [ ] **Step 5: Sync, drift, run both Odoos**

```bash
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && tools/odoo_install_test.sh 16 && tools/odoo_install_test.sh 15
```
Expected: `RESULT v16 PASS`, `RESULT v15 PASS`. If view validation fails, the error names the offending attribute — fix the XML, not the test.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "v15, v16: attrs views, env._t, v15 recordset dispatch

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 9: v14 — the legacy-web-client reference (family A)

**Files:**
- Create: `v14/pentaho_reports/**` from v15; replace `static/src/js/action_service.js` with `static/src/js/action_manager.js`; create `views/assets.xml`; edit `__manifest__.py`

**Interfaces:**
- Produces: `static/src/js/action_manager.js` (legacy `odoo.define` module `pentaho_reports.ActionManager`) that v13/v12/v11 copy and tweak. Same server contract: `render_report` → `[content_b64, output_type, filename, direct_print]`; `/pentaho/download` POST with `data` (JSON array) + `token`; `/pentaho/print?data=...` GET.

- [ ] **Step 1: Install reportlab into the broken odoo14 venv (the one sanctioned venv change)**

```bash
/Volumes/Workspace/Development/OdooWorkbench/odoo14/venv/bin/python -c "import reportlab" 2>/dev/null && echo present || /Volumes/Workspace/Development/OdooWorkbench/odoo14/venv/bin/python -m pip install -q "reportlab==3.5.55" && /Volumes/Workspace/Development/OdooWorkbench/odoo14/venv/bin/python -c "import reportlab; print(reportlab.Version)"
```
Expected: `3.5.55`.

- [ ] **Step 2: Copy v15 → v14 and apply mechanical edits**

```bash
rm -rf v14 && mkdir -p v14 && cp -R v15/pentaho_reports v14/pentaho_reports && find v14 -name __pycache__ -type d -prune -exec rm -rf {} +
sed -i '' "s/'version': '15.0.2.0.0'/'version': '14.0.2.0.0'/" v14/pentaho_reports/__manifest__.py
mv v14/pentaho_reports/migrations/15.0.2.0.0 v14/pentaho_reports/migrations/14.0.2.0.0
sed -i '' "s/Odoo 15/Odoo 14/g; s/\*\*15\*\*/**14**/; s/Python ≥ 3.7 (Odoo 14's own floor)/Python ≥ 3.6 (Odoo 14's own floor)/; s/\/v15/\/v14/" v14/pentaho_reports/README.md
rm v14/pentaho_reports/static/src/js/action_service.js
```

- [ ] **Step 3: Manifest — XML asset bundle instead of the `assets` key**

In `v14/pentaho_reports/__manifest__.py` delete the whole `'assets': {...},` block and set:
```python
    'data': [
        'views/assets.xml',
        'views/report_views.xml',
    ],
```

- [ ] **Step 4: `views/assets.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="assets_backend" name="pentaho_reports assets" inherit_id="web.assets_backend">
        <xpath expr="." position="inside">
            <script type="text/javascript" src="/pentaho_reports/static/src/js/print_min.js"/>
            <script type="text/javascript" src="/pentaho_reports/static/src/js/action_manager.js"/>
        </xpath>
    </template>
</odoo>
```

- [ ] **Step 5: `static/src/js/action_manager.js` (Odoo 13/14 flavour)**

```javascript
odoo.define('pentaho_reports.ActionManager', function (require) {
"use strict";

/**
 * Pentaho report actions on the legacy web client (Odoo 12-14).
 *
 * Core's ReportActionManager handles qweb-* types only and rejects anything
 * else (console.error + Promise.reject), so we layer an include on top of it
 * (the explicit require pins the load order) and take over report_type
 * 'pentaho': ORM call render_report → file download through /pentaho/download
 * (session.get_file POSTs a form with `token` + `csrf_token`; the route
 * answers with the fileToken cookie that unblocks the UI) or direct print.
 */
var ActionManager = require('web.ActionManager');
require('web.ReportActionManager');
var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');

var _t = core._t;

function getBrowserInfo() {
    var ua = navigator.userAgent.toLowerCase();
    return {
        isFirefox: ua.indexOf('firefox') > -1,
        isChrome: ua.indexOf('chrome') > -1 && ua.indexOf('edg') === -1,
        isEdge: ua.indexOf('edg') > -1,
        isSafari: ua.indexOf('safari') > -1 && ua.indexOf('chrome') === -1,
    };
}

/** Open the PDF in a new tab through /pentaho/print (Firefox prints from there). */
function printPDFInNewWindow(contentB64, outputType, fileName) {
    return new Promise(function (resolve, reject) {
        var url = '/pentaho/print?data=' + encodeURIComponent(JSON.stringify([contentB64, outputType, fileName]));
        var win = window.open(url, '_blank');
        if (!win) {
            reject(new Error(_t('Popup blocked. Please allow popups for this site.')));
            return;
        }
        var check = setInterval(function () {
            if (win.closed) { clearInterval(check); resolve(); }
        }, 500);
        setTimeout(function () { clearInterval(check); resolve(); }, 30000);
    });
}

/** Print.js (bundled as print_min.js) for Chrome/Edge. */
function printWithPrintJS(contentB64) {
    return new Promise(function (resolve, reject) {
        if (!window.printJS) {
            reject(new Error('Print.js not loaded'));
            return;
        }
        try {
            window.printJS({
                printable: contentB64,
                type: 'pdf',
                base64: true,
                onPrintDialogClose: resolve,
                onError: reject,
            });
        } catch (e) {
            reject(e);
        }
    });
}

function downloadReport(contentB64, outputType, fileName) {
    return new Promise(function (resolve, reject) {
        var ok = session.get_file({
            url: '/pentaho/download',
            data: { data: JSON.stringify([contentB64, outputType, fileName]) },
            success: resolve,
            error: function (error) { reject(error); },
            complete: framework.unblockUI,
        });
        if (!ok) {
            reject(new Error(_t('A popup window with your report was blocked.')));
        }
    });
}

ActionManager.include({
    /**
     * @override
     */
    _executeReportAction: function (action, options) {
        if (action.report_type !== 'pentaho') {
            return this._super.apply(this, arguments);
        }
        return this._executePentahoReportAction(action, options);
    },

    _executePentahoReportAction: function (action, options) {
        var self = this;
        var context = action.context || {};
        var data = action.data || {};
        var activeIds = context.active_ids || [];

        framework.blockUI();
        return this._rpc({
            model: 'ir.actions.report',
            method: 'search_read',
            args: [[['report_name', '=', action.report_name]], ['id']],
            kwargs: { limit: 1 },
        }).then(function (reports) {
            if (!reports.length) {
                throw new Error(_t('Report %s not found').replace('%s', action.report_name));
            }
            return self._rpc({
                model: 'ir.actions.report',
                method: 'render_report',
                args: [reports[0].id, activeIds, data],
                context: context,
            });
        }).then(function (result) {
            if (!result) {
                throw new Error(_t('No data returned from report'));
            }
            var contentB64 = result[0], outputType = result[1], fileName = result[2], directPrint = result[3];
            if (data.variables && data.variables.filename) {
                fileName = data.variables.filename.replace(/\.[^/.]+$/, '');
            }
            if (directPrint && outputType === 'pdf') {
                var browser = getBrowserInfo();
                var printing = browser.isFirefox
                    ? printPDFInNewWindow(contentB64, outputType, fileName)
                    : printWithPrintJS(contentB64).catch(function () {
                        return printPDFInNewWindow(contentB64, outputType, fileName);
                    });
                return printing.then(function () {
                    framework.unblockUI();
                    self.displayNotification({ type: 'success', title: _t('Report'), message: _t('Report sent to printer') });
                }, function () {
                    self.displayNotification({ type: 'warning', title: _t('Report'), message: _t('Print failed. Downloading file instead.') });
                    return downloadReport(contentB64, outputType, fileName);
                });
            }
            return downloadReport(contentB64, outputType, fileName);
        }).then(function () {
            if (action.close_on_report_download) {
                return self.doAction({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));
            }
            if (options && options.on_close) {
                options.on_close();
            }
        }).guardedCatch(function (error) {
            framework.unblockUI();
            var message = (error && error.message) || (error && error.data && error.data.message) || _t('Unknown error');
            self.displayNotification({ type: 'danger', title: _t('Error generating report'), message: message, sticky: true });
        });
    },
});

});
```

- [ ] **Step 6: Dispatch hook is already the recordset form (inherited from v15) — verify**

```bash
grep -n "def _render_pentaho\|def render_pentaho" v14/pentaho_reports/models/ir_actions_report.py
```
Expected: `def _render_pentaho(self, res_ids, data=None):` (correct for Odoo 14).

- [ ] **Step 7: Sync, drift, run Odoo 14**

```bash
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && tools/odoo_install_test.sh 14
```
Expected: `RESULT v14 PASS`. Asset-bundle errors surface in the log as `web.assets_backend` / `AssetsBundle` lines — if present, the JS file has a syntax error; fix it. (Odoo 14 minifies JS at bundle time only when the bundle is requested; the HttpCase tests request `/web` pages indirectly via `authenticate`, which is enough to compile the bundle on most versions — additionally run `node --check v14/pentaho_reports/static/src/js/action_manager.js` if `node` is available.)

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "v14: legacy ActionManager include, XML asset bundle

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 10: v13 and v12

**Files:**
- Create: `v13/pentaho_reports/**`, `v12/pentaho_reports/**` from v14; edit `models/ir_actions_report.py` (both), `static/src/js/action_manager.js` (v12 only)

**Interfaces:** identical, except dispatch hook `render_pentaho(self, res_ids, data=None)` (no underscore — Odoo 11–13 `render()` looks up `render_<type>`).

- [ ] **Step 1: Copy and mechanical edits**

```bash
for N in 13 12; do
  rm -rf v$N && mkdir -p v$N && cp -R v14/pentaho_reports v$N/pentaho_reports && find v$N -name __pycache__ -type d -prune -exec rm -rf {} +
  sed -i '' "s/'version': '14.0.2.0.0'/'version': '$N.0.2.0.0'/" v$N/pentaho_reports/__manifest__.py
  mv v$N/pentaho_reports/migrations/14.0.2.0.0 v$N/pentaho_reports/migrations/$N.0.2.0.0
  sed -i '' "s/Odoo 14/Odoo $N/g; s/\*\*14\*\*/**$N**/; s/\/v14/\/v$N/" v$N/pentaho_reports/README.md
done
sed -i '' "s/Python ≥ 3.6 (Odoo 12's own floor)/Python ≥ 3.6 (this build's floor; Odoo 12 itself allows 3.5, which the shared renderer does not support)/" v12/pentaho_reports/README.md
```

- [ ] **Step 2: Model (both) — drop `ondelete`, rename the dispatch hook**

In `models/ir_actions_report.py` of v13 and v12:
```python
    report_type = fields.Selection(
        selection_add=[('pentaho', 'Pentaho Report')],
    )
```
and replace the `_render_pentaho` method with:
```python
    def render_pentaho(self, res_ids, data=None):
        """Odoo 11-13 generic dispatch: ir.actions.report.render(res_ids, data)
        calls render_<report_type>(res_ids, data) on the report record."""
        return self._render_pentaho_report(res_ids, data)
```

- [ ] **Step 3: v12 only — rewrite the JS for jQuery 1.11 Deferreds and `do_notify`/`do_warn`**

Odoo 12's `_rpc` returns a jQuery 1.11 Deferred: it does **not** assimilate native Promises returned from `.then` callbacks, has no `.catch`/`.guardedCatch`, and does **not** catch exceptions thrown inside callbacks. So the v12 file cannot be a find-and-replace of v14's — replace `v12/pentaho_reports/static/src/js/action_manager.js` entirely with:

```javascript
odoo.define('pentaho_reports.ActionManager', function (require) {
"use strict";

/**
 * Pentaho report actions on the legacy web client (Odoo 12).
 *
 * Core's ReportActionManager handles qweb-* types only and rejects anything
 * else, so we layer an include on top of it (the explicit require pins the
 * load order) and take over report_type 'pentaho': ORM call render_report →
 * file download through /pentaho/download (session.get_file POSTs a form
 * with `token` + `csrf_token`; the route answers with the fileToken cookie
 * that unblocks the UI) or direct print.
 *
 * Everything is jQuery 1.11 Deferreds ($.Deferred / .then(ok, fail)):
 * native Promises would not chain through _rpc's deferreds.
 */
var ActionManager = require('web.ActionManager');
require('web.ReportActionManager');
var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');

var _t = core._t;

function rejected(message) {
    return $.Deferred().reject(new Error(message)).promise();
}

function getBrowserInfo() {
    var ua = navigator.userAgent.toLowerCase();
    return {
        isFirefox: ua.indexOf('firefox') > -1,
        isChrome: ua.indexOf('chrome') > -1 && ua.indexOf('edg') === -1,
        isEdge: ua.indexOf('edg') > -1,
        isSafari: ua.indexOf('safari') > -1 && ua.indexOf('chrome') === -1,
    };
}

/** Open the PDF in a new tab through /pentaho/print (Firefox prints from there). */
function printPDFInNewWindow(contentB64, outputType, fileName) {
    var def = $.Deferred();
    var url = '/pentaho/print?data=' + encodeURIComponent(JSON.stringify([contentB64, outputType, fileName]));
    var win = window.open(url, '_blank');
    if (!win) {
        return rejected(_t('Popup blocked. Please allow popups for this site.'));
    }
    var check = setInterval(function () {
        if (win.closed) { clearInterval(check); def.resolve(); }
    }, 500);
    setTimeout(function () { clearInterval(check); def.resolve(); }, 30000);
    return def.promise();
}

/** Print.js (bundled as print_min.js) for Chrome/Edge. */
function printWithPrintJS(contentB64) {
    var def = $.Deferred();
    if (!window.printJS) {
        return rejected('Print.js not loaded');
    }
    try {
        window.printJS({
            printable: contentB64,
            type: 'pdf',
            base64: true,
            onPrintDialogClose: function () { def.resolve(); },
            onError: function (error) { def.reject(error); },
        });
    } catch (e) {
        def.reject(e);
    }
    return def.promise();
}

function downloadReport(contentB64, outputType, fileName) {
    var def = $.Deferred();
    var ok = session.get_file({
        url: '/pentaho/download',
        data: { data: JSON.stringify([contentB64, outputType, fileName]) },
        success: function () { def.resolve(); },
        error: function (error) { def.reject(error); },
        complete: framework.unblockUI,
    });
    if (!ok) {
        return rejected(_t('A popup window with your report was blocked.'));
    }
    return def.promise();
}

ActionManager.include({
    /**
     * @override
     */
    _executeReportAction: function (action, options) {
        if (action.report_type !== 'pentaho') {
            return this._super.apply(this, arguments);
        }
        return this._executePentahoReportAction(action, options);
    },

    _executePentahoReportAction: function (action, options) {
        var self = this;
        var context = action.context || {};
        var data = action.data || {};
        var activeIds = context.active_ids || [];

        framework.blockUI();
        return this._rpc({
            model: 'ir.actions.report',
            method: 'search_read',
            args: [[['report_name', '=', action.report_name]], ['id']],
            kwargs: { limit: 1 },
        }).then(function (reports) {
            if (!reports.length) {
                return rejected(_t('Report %s not found').replace('%s', action.report_name));
            }
            return self._rpc({
                model: 'ir.actions.report',
                method: 'render_report',
                args: [reports[0].id, activeIds, data],
                context: context,
            });
        }).then(function (result) {
            if (!result) {
                return rejected(_t('No data returned from report'));
            }
            var contentB64 = result[0], outputType = result[1], fileName = result[2], directPrint = result[3];
            if (data.variables && data.variables.filename) {
                fileName = data.variables.filename.replace(/\.[^/.]+$/, '');
            }
            if (directPrint && outputType === 'pdf') {
                var browser = getBrowserInfo();
                var printing = browser.isFirefox
                    ? printPDFInNewWindow(contentB64, outputType, fileName)
                    : printWithPrintJS(contentB64).then(null, function () {
                        return printPDFInNewWindow(contentB64, outputType, fileName);
                    });
                return printing.then(function () {
                    framework.unblockUI();
                    self.do_notify(_t('Report'), _t('Report sent to printer'));
                }, function () {
                    self.do_warn(_t('Report'), _t('Print failed. Downloading file instead.'));
                    return downloadReport(contentB64, outputType, fileName);
                });
            }
            return downloadReport(contentB64, outputType, fileName);
        }).then(function () {
            if (action.close_on_report_download) {
                return self.doAction({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));
            }
            if (options && options.on_close) {
                options.on_close();
            }
        }, function (error) {
            framework.unblockUI();
            var message = (error && error.message) || (error && error.data && error.data.message) || _t('Unknown error');
            self.do_warn(_t('Error generating report'), message, true);
            return $.Deferred().reject(error).promise();
        });
    },
});

});
```

- [ ] **Step 4: Sync, drift, run both Odoos**

```bash
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && tools/odoo_install_test.sh 13 && tools/odoo_install_test.sh 12
```
Expected: `RESULT v13 PASS`, `RESULT v12 PASS`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "v12, v13: render_pentaho dispatch, no selection ondelete, v12 do_notify/do_warn

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 11: v11

**Files:**
- Create: `v11/pentaho_reports/**` from v12; edit `models/ir_actions_report.py`, `static/src/js/action_manager.js`, `__manifest__.py`

**Interfaces:** identical; `create(self, vals)` is single-record (`@api.model`).

- [ ] **Step 1: Copy and mechanical edits**

```bash
rm -rf v11 && mkdir -p v11 && cp -R v12/pentaho_reports v11/pentaho_reports && find v11 -name __pycache__ -type d -prune -exec rm -rf {} +
sed -i '' "s/'version': '12.0.2.0.0'/'version': '11.0.2.0.0'/" v11/pentaho_reports/__manifest__.py
mv v11/pentaho_reports/migrations/12.0.2.0.0 v11/pentaho_reports/migrations/11.0.2.0.0
sed -i '' "s/Odoo 12/Odoo 11/g; s/\*\*12\*\*/**11**/; s/\/v12/\/v11/" v11/pentaho_reports/README.md
```

- [ ] **Step 2: Model — Odoo 11 `create`**

In `v11/pentaho_reports/models/ir_actions_report.py` replace the `create` method with:
```python
    @api.model
    def create(self, vals):
        if vals.get('report_type') == 'pentaho':
            vals['type'] = 'ir.actions.report'
        record = super(IrActionsReport, self).create(vals)
        record._load_pentaho_files()
        return record
```
and make the `write` override's `super()` call explicit: `res = super(IrActionsReport, self).write(vals)`.

- [ ] **Step 3: JS — Odoo 11 hooks `ir_actions_report` (core's qweb handling lives in `report.report`)**

In `v11/pentaho_reports/static/src/js/action_manager.js`:
- replace `require('web.ReportActionManager');` with `require('report.report');  // core qweb handling; our include must layer on top of it`
- replace the `_executeReportAction` override with:
```javascript
    ir_actions_report: function (action, options) {
        if (action.report_type !== 'pentaho') {
            return this._super.apply(this, arguments);
        }
        return this._executePentahoReportAction(action, options);
    },
```
- in `_executePentahoReportAction`, replace `return self.doAction({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));` with `return self.do_action({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));` (Odoo 11's method is `do_action`).
- update the header comment to `Odoo 11`. (The jQuery-Deferred structure inherited from v12 is exactly what Odoo 11 needs too.)

- [ ] **Step 4: Python-3.6 check of the whole v11 folder with Odoo 11's interpreter, then run Odoo 11**

```bash
/Volumes/Workspace/Development/OdooWorkbench/odoo11/venv/bin/python -m compileall -q v11/pentaho_reports && echo V11_COMPILE_OK
python3 tools/sync_native.py >/dev/null && python3 tools/check_drift.py && tools/odoo_install_test.sh 11
```
Expected: `V11_COMPILE_OK`, `RESULT v11 PASS`. Odoo 11 has no `--test-tags`, so the harness runs with `--test-enable` only; confirm in the log that `TestPentahoRender`/`TestPentahoControllers` ran (`grep -c "pentaho_reports.tests" …/odoo_v11.log` > 0).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "v11: single-record create, ir_actions_report include on report.report

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```

---

### Task 12: `tools/test_matrix.sh`, root README, full matrix run

**Files:**
- Create: `tools/test_matrix.sh`
- Replace: `README.md` (root)

**Interfaces:**
- Produces: `tools/test_matrix.sh` (no args; exit 0 iff every step passes; prints a final table). Steps: drift → compileall per folder with its venv (+ `engine/native` with py3.6) → `tools/engine_matrix.sh` → `tools/odoo_install_test.sh 11..19`.

- [ ] **Step 1: Write `tools/test_matrix.sh`**

```bash
#!/usr/bin/env bash
# The acceptance run for "pentaho_reports works on Odoo 11-19".
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
WB=/Volumes/Workspace/Development/OdooWorkbench
PY36=/Library/Frameworks/Python.framework/Versions/3.6/bin/python3
rows=(); fail=0
mark() { rows+=("$1|$2"); [ "$2" = PASS ] || fail=1; }

echo "### 1. drift"
python3 tools/check_drift.py && mark drift PASS || mark drift FAIL

echo "### 2. compileall per folder (each Odoo's own interpreter) + engine on py3.6"
"$PY36" -m compileall -q engine/native && mark "compile engine@py3.6" PASS || mark "compile engine@py3.6" FAIL
for N in 11 12 13 14 15 16 17 18 19; do
  PY="$WB/odoo$N/venv/bin/python"
  if [ -x "$PY" ] && "$PY" -m compileall -q "v$N/pentaho_reports"; then mark "compile v$N" PASS; else mark "compile v$N" FAIL; fi
done
find . -name __pycache__ -type d -prune -exec rm -rf {} +

echo "### 3. engine matrix (Python × reportlab)"
tools/engine_matrix.sh && mark "engine matrix" PASS || mark "engine matrix" FAIL

echo "### 4. install + module tests on each Odoo (throwaway DBs)"
for N in 11 12 13 14 15 16 17 18 19; do
  if tools/odoo_install_test.sh "$N"; then mark "odoo v$N install+tests" PASS; else mark "odoo v$N install+tests" FAIL; fi
done

echo; echo "==================== pentaho_reports test matrix ===================="
for r in "${rows[@]}"; do IFS='|' read -r k v <<<"$r"; printf "  %-32s %s\n" "$k" "$v"; done
echo "====================================================================="
exit $fail
```

- [ ] **Step 2: Root `README.md`**

```markdown
# pentaho_odoo_workbench

`pentaho_reports` — render Pentaho Report Designer `.prpt` files to PDF **inside Odoo with a
pure-Python engine**: no Java, no Tomcat, no external report server. It runs anywhere Odoo runs,
including Odoo.sh.

One module, built for every supported Odoo:

| Folder | Odoo | Python floor of the build | Verified locally with |
|---|---|---|---|
| `v11/pentaho_reports` | 11.0 | 3.6 (Odoo 11 allows 3.5 — not supported here) | Python 3.6.8 · reportlab 3.5.59 |
| `v12/pentaho_reports` | 12.0 | 3.6 | Python 3.9 · reportlab 5.0.0 |
| `v13/pentaho_reports` | 13.0 | 3.6 | Python 3.9 · reportlab 4.4.10 |
| `v14/pentaho_reports` | 14.0 | 3.6 | Python 3.9 · reportlab 3.5.55 |
| `v15/pentaho_reports` | 15.0 | 3.7 | Python 3.9 · reportlab 3.5.59 |
| `v16/pentaho_reports` | 16.0 | 3.7 | Python 3.9 · reportlab 3.5.59 |
| `v17/pentaho_reports` | 17.0 | 3.10 | Python 3.10 · reportlab 3.6.8 |
| `v18/pentaho_reports` | 18.0 | 3.10 | Python 3.12 · reportlab 4.1.0 |
| `v19/pentaho_reports` | 19.0 | 3.10 | Python 3.12 · reportlab 4.1.0 |

## Install

Copy the folder for your version into your addons path (or add `--addons-path=/path/to/vNN`),
update the app list, install **Pentaho Reports**. Then Settings → Technical → Reports → create a
report with type *Pentaho Report*, upload the `.prpt`, set the model so it appears in that model's
Print menu. Python API: `env['ir.actions.report']._render_pentaho_report(ids)` on a report record.

Odoo.sh note: Odoo.sh only auto-loads modules at the root of a repository, so copy
`vNN/pentaho_reports` into the root of your own Odoo.sh repository.

## How the repo is organised

- `engine/native/` — the **one** canonical renderer (parser `bundle.py`, `renderer.py`, `painter.py`, …)
  and its pytest suite. Python ≥ 3.6 only: see `engine/native/COMPAT.md`.
- `vNN/pentaho_reports/native/` — byte-identical copies made by `python3 tools/sync_native.py`.
  **Never edit them**; `python3 tools/check_drift.py` (and a pytest) fails on any difference.
- `vNN/pentaho_reports/{models,controllers,views,static,tests}` — the per-version Odoo glue
  (three families: legacy web client 11–14, OWL 15–16, OWL + Python-expression views 17–19).
- `fixtures/` — real `.prpt` files with credentials scrubbed (`tools/scrub_fixture.py`).
- `docs/superpowers/specs/` — the design and the per-version Odoo API survey with file:line evidence.

## Verifying

`tools/test_matrix.sh` is the acceptance run: drift check → `compileall` of each folder with that
Odoo's interpreter → engine tests across Python 3.6/3.9/3.10/3.12 × reportlab 3.5/3.6/4.1/4.4/5.0
(`tools/engine_matrix.sh`) → install + module tests on each local Odoo in a throwaway database
(`tools/odoo_install_test.sh NN`). Local paths are the Workbench ones
(`/Volumes/Workspace/Development/OdooWorkbench/odooNN`).

Engine tests alone: `cd engine/native/tests && python -m pytest` (needs reportlab, pypdf, pytest).

## Contributing a renderer change

1. Edit `engine/native/…` and its tests. 2. `python3 tools/sync_native.py`. 3. `tools/test_matrix.sh`.
```

- [ ] **Step 3: Run the full matrix**

```bash
chmod +x tools/test_matrix.sh && tools/test_matrix.sh 2>&1 | tail -30
```
Expected: every row `PASS` (drift, compile engine@py3.6, compile v11…v19, engine matrix, odoo v11…v19 install+tests). Paste the final table into the task report verbatim. Any FAIL must be fixed at its root (engine, glue, or harness) and the whole matrix re-run.

- [ ] **Step 4: Confirm no throwaway databases remain and the tree is clean**

```bash
psql -tAc "select datname from pg_database where datname like 'pentaho_test_%'" postgres; git status --short | wc -l
```
Expected: no rows; `0`.

- [ ] **Step 5: Commit** (no push — the branch is integrated at the end via finishing-a-development-branch)

```bash
git add -A && git commit -m "Add test_matrix.sh acceptance run and root README (Odoo 11-19 matrix)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC" && git log --oneline -1
```

---

## Self-review against the spec

- §2 decisions (folders, one engine, 3.6 floor, throwaway DBs): Tasks 1, 3, 6–11, 12 ✔
- §3 layout incl. `engine/native`, `fixtures/`, `tools/*`, per-folder README, migrations `NN.0.2.0.0`: Tasks 1, 2, 5, 6–12 ✔
- §4 engine port + fixtures + conftest skip behaviour + sync/drift: Tasks 1–3, 5 ✔ (`_Record` keeps kwargs/eq/repr; `_FixturePath.read_bytes` skips)
- §5 families: C (v17–19) Tasks 6–7 · B (v15–16) Task 8 · A (v11–14) Tasks 9–11; shared `render_report`/`_render_pentaho_report`, dispatch aliases per version, `fileToken` cookie, v19 `jsonrpc`, `ondelete` only 14+, v11 `create(vals)`, `external_dependencies` ✔
- §6 module tests: Task 6 (version-agnostic `test_render.py` + `test_controllers.py`, `partner_list.prpt` from Task 5; `tagged` fallback; `group_ids`/`groups_id` detection; cookie assertion) ✔
- §7 matrix steps 1–5: Tasks 4, 6 (harness), 12 ✔ (odoo14 reportlab install in Task 9 Step 1)
- §8 docs: Task 12 root README, per-folder README from Task 6 onward, `PORT_CHANGES.md` moved in Task 1 ✔
- Type/name consistency: `_render_pentaho_report(res_ids, data=None)` used identically in Tasks 6, 8, 10, 11 and in the tests' dispatch check; harness script name `tools/odoo_install_test.sh NN` used by Tasks 6–12 ✔

---

### Task 13: Make the repository self-documenting (added 2026-08-21 at the user's request)

**Why:** the repo must stand alone in development — everything about how and why it was made, how to extend it (e.g. a future `v20/`), and how an LLM agent should work in it must live IN the repo, not in a person's or an assistant's memory.

**Files:**
- Create: `CLAUDE.md` (repo root; also the file Claude Code loads automatically), `docs/ARCHITECTURE.md`, `docs/ADDING-A-VERSION.md`, `docs/DECISIONS.md`, `docs/LESSONS.md`, `docs/HISTORY.md`, `docs/build-log/README.md`, `docs/build-log/2026-08-21-sdd-ledger.md`, `docs/build-log/reports/task-N-report.md` (N = 1..13, copied from `.superpowers/sdd/2026-08-21-per-version-layout/`)
- Modify: root `README.md` (add a "Documentation map" section linking the above; keep everything else)

**Interfaces:**
- Consumes: the whole repo as built (read `git log --stat`, the spec, the plan, the API survey, the SDD ledger `.superpowers/sdd/2026-08-21-per-version-layout/progress.md`, every `task-N-report.md`, `tools/*`, every `vNN/pentaho_reports` glue file, `engine/native/COMPAT.md`).
- Produces: documents only. No code or tool behaviour changes. Every statement must be verifiable against the repo; cite paths.

**Sources of truth the docs must be consistent with (and link to):** `docs/superpowers/specs/2026-08-21-per-version-layout-design.md` (design), `docs/superpowers/specs/2026-08-21-odoo-version-api-survey.md` (per-version API facts with file:line evidence), `docs/superpowers/plans/2026-08-21-per-version-layout.md` (this plan), `docs/PORT_CHANGES.md` (the 2026-08-12 pure-Python fidelity port), `engine/native/COMPAT.md`.

- [ ] **Step 1: `CLAUDE.md` — the entry point for an LLM agent (≤ 150 lines)**

Sections, in this order: (1) *What this repo is* — `pentaho_reports`, pure-Python renderer for Pentaho `.prpt` reports inside Odoo (no Java/Tomcat/external service; Odoo.sh-friendly), shipped as nine per-version folders `v11`…`v19`. (2) *Layout* — the tree from this plan's "File structure" section, one line per entry. (3) *The three rules* — (a) `engine/native/` is the ONLY place engine code is edited; `vNN/pentaho_reports/native/` are synced copies (`python3 tools/sync_native.py`), `python3 tools/check_drift.py` must pass; (b) engine floor is Python 3.6 (`engine/native/COMPAT.md`), glue for v11 too; (c) glue comes in three families — table: family / versions / JS mechanism / assets / view attrs / route type / dispatch hook / create decorator / `ondelete` — copied from `docs/ARCHITECTURE.md`. (4) *How to verify* — `pytest` (engine, from repo root), `tools/engine_matrix.sh`, `tools/odoo_install_test.sh NN`, `tools/test_matrix.sh`; local paths assumed (`/Volumes/Workspace/Development/OdooWorkbench/odooNN/{odoo,venv}`, Postgres roles `odooNN`, throwaway DBs `pentaho_test_vNN`). (5) *How to change things* — engine change: edit → pytest → sync → drift → matrix; glue change: edit the family's reference (v19 for 17–19, v16 for 15–16, v14 for 12–14, v11 alone) then replay to siblings and re-run each sibling's harness; never hand-edit a synced `native/`. (6) *Adding a new Odoo version* → `docs/ADDING-A-VERSION.md`. (7) *Conventions* — `_('…%s') % x` only; BSD `sed -i ''` on macOS; bash 3.2 `${arr[@]+"${arr[@]}"}`; commit trailers used in this repo; fixtures must be credential-scrubbed (`tools/scrub_fixture.py`); don't reformat untouched files. (8) *Where the memory lives* — `docs/HISTORY.md`, `docs/DECISIONS.md`, `docs/LESSONS.md`, `docs/build-log/`.

- [ ] **Step 2: `docs/ARCHITECTURE.md`**

(1) Intention: the problem (Pentaho reports needed a Java server; Odoo.sh cannot run one) and the solution (pure-Python engine; one module per Odoo version). (2) Component map: engine (`bundle.py` parser → `model.py` → `renderer.py`/`painter.py` via reportlab; `query.py` SQL placeholder handling; `fonts.py`, `formats.py`), glue (model, controller routes `/pentaho/preview|download|print`, views, JS, tests), tools. (3) The families table — definitive, filled from the code as built (verify each cell by grepping the nine folders; include: JS file name + mechanism; `_t` source; assets declaration; view attribute syntax; preview route type; `selection_add` `ondelete`; `create` decorator; dispatch hook name + signature; notification API; error-handling idiom (native Promise + `.catch` on 13–14, jQuery Deferred + `(error, event)` on 11–12, OWL registry on 15+)). (4) Data flow of a print: Print menu → JS handler resolves report by `report_name` → `render_report` → `_render_pentaho_report` → `NativeRenderer` → base64 → `/pentaho/download` (with the `fileToken` cookie contract) or Print.js / `/pentaho/print`. (5) Test strategy: engine pytest + fixtures (scrubbed real reports + synthetic `partner_list.prpt`), engine matrix (Python × reportlab), per-version module tests (version-agnostic design: `tagged` fallback, `group_ids`/`groups_id` detection, JSON via `self.opener`, dispatch-shape detection), the install harness and what "PASS" means. (6) Environment matrix table (Odoo → Python → reportlab → harness flags: `--longpolling-port`/`--gevent-port`, `--limit-memory-hard=0` on Darwin <16, PIL shim ≤12, `--test-tags` ≥12). (7) Known limits / out of scope (from the spec §9).

- [ ] **Step 3: `docs/ADDING-A-VERSION.md` — the v20 playbook**

Written so an agent with no other context can do it. (1) *Survey first*: reproduce the per-version API survey for the new version — include the exact questionnaire (the fields of the survey schema: python floor; report-action JS mechanism + how to intercept a custom `report_type` + download helper + block UI + notification + ES-module support; assets declaration; view conditional-attribute syntax + form/search xmlids; JSON route type + `content_disposition` + `make_response`; `model_create_multi`, `selection_add`/`ondelete`, `cr.savepoint()`, `addons_path` type, `has_group`, `res.users.share`, `_()` arity; report model name, `report_type` values, render dispatch name+signature, Binary attachment default, bindings; tests: TransactionCase conventions, HttpCase JSON posting, `tagged`, run command) and the grep starting points (`odoo/http.py`, `odoo/fields.py`, `odoo/api.py`, `addons/base/models/ir_actions_report.py`, `addons/base/models/ir_ui_view.py`, `addons/web/static/src/webclient/actions/action_service.js`, `odoo/tests/common.py`, `odoo/tools/config.py`, `setup.py`). Point at `docs/superpowers/specs/2026-08-21-odoo-version-api-survey.md` for what the answers looked like for 11–19. (2) *Pick the nearest family sibling* (for v20: copy `v19`). (3) *Mechanical edits*: manifest version `20.0.2.0.0`; `migrations/20.0.2.0.0/`; README. (4) *Decision checklist* — for each API point, what to do if the survey answer differs from the sibling (e.g. route type renamed → change decorator; `res.users` field renamed → tests already detect `group_ids`/`groups_id`, extend the detector; `_render` dispatch signature changed → add the new hook shape AND extend `test_core_render_dispatch_finds_pentaho`; view syntax changed → rewrite `views/report_views.xml`; `_get_readable_fields` needed if the JS reads a new action field). (5) *Wire the tooling*: `VERSIONS` in `tools/sync_native.py` and `tools/check_drift.py`; `tools/odoo_install_test.sh` (port `180NN`, flags), `tools/test_matrix.sh` loops, `tools/engine_matrix.sh` (add the new Python × reportlab pair), root README table, `CLAUDE.md` family table. (6) *Prove it*: `python3 tools/sync_native.py && python3 tools/check_drift.py && tools/odoo_install_test.sh 20`, then `tools/test_matrix.sh`. (7) *Engine floor policy*: when the oldest supported version is dropped, raise the floor in `engine/native/COMPAT.md` and the matrix. (8) A worked example: the concrete diff list between v18 and v19 as it exists in the repo (route type, README, manifest, migrations) and between v14 and v15 (the big family jump) — obtained with `diff -r -x __pycache__`.

- [ ] **Step 4: `docs/DECISIONS.md` — decision log**

One entry per decision, format: *Decision — Date — Context — Alternatives considered — Why — Cost if wrong*. Must include: folders not Odoo.sh branches; one engine with nine real copies (not symlinks, not two flavours); Python 3.6 floor (not 3.5, not 3.7+); throwaway DBs as acceptance; `engine/native/` (package keeps import name); vendored + credential-scrubbed fixtures; synthetic `partner_list.prpt` instead of Piaggio-bound tests; version-agnostic module tests; resolve reports by `report_name` in JS; dispatch aliases per version; `fileToken` cookie kept; v19 `jsonrpc`; harness shims (`--limit-memory-hard=0`, PIL `sitecustomize`, pytest.ini testpaths) instead of venv changes — and the single sanctioned venv change (odoo14 reportlab 3.5.55); `.catch` instead of `guardedCatch`; `errorMessage()` + `preventDefault`; every `Ruling:` line from the SDD ledger (`.superpowers/sdd/2026-08-21-per-version-layout/progress.md`), each rewritten as a full entry.

- [ ] **Step 5: `docs/LESSONS.md` — gotchas discovered while building (each: symptom → cause → fix → where it lives in the repo)**

At minimum: Pillow ≥10 removed `Image.ANTIALIAS` and Odoo ≤12 core needs it; Odoo ≤15 `setrlimit(RLIMIT_RSS)` EINVAL on macOS; bash 3.2 + `set -u` + empty arrays; Odoo 13/14 `guardedCatch` skips `Error` rejections; `_rpc` rejection shapes per version (`{message, event}` on 13+, `(error, $.Event())` on 11–12) and `event.preventDefault()` to avoid the double crash dialog; jQuery 1.11 Deferreds don't assimilate native Promises and don't catch thrown errors; Odoo 16+ test mode 400s requests lacking the test-request-key cookie (use `self.opener`); Odoo `--logfile` appends; py3.6's bootstrap pip corrupts Pillow dylibs when upgraded in the same invocation; reportlab 3.5.55 needs `CFLAGS=-Wno-error=implicit-function-declaration` on current Clang; Odoo 19 `group_ids`; Odoo 19 `jsonrpc` route type; `_()` single-arg on 11–13; `ondelete` required from 14; view `attrs` rejected from 17 / python-expr rejected before 17; real `.prpt` files embed DB credentials; duplicate test basenames across synced copies break bare pytest (→ `pytest.ini`); fixtures outside the repo silently erroring; `from __future__ import annotations` hides 3.10-only annotation syntax.

- [ ] **Step 6: `docs/HISTORY.md` + `docs/build-log/`**

`HISTORY.md`: timeline — the original Java-based willowit module; the 2026-08-12 pure-Python renderer + fidelity port (link `docs/PORT_CHANGES.md`); the 2026-08-21 per-version layout (link spec, plan, survey); how it was built (brainstorm → spec → plan → subagent-driven development with a review per task; 9-agent source survey of the local Odoo trees); commit range on `feat/odoo-11-19-layout`. `docs/build-log/README.md` explains what the folder holds. Copy `.superpowers/sdd/2026-08-21-per-version-layout/progress.md` → `docs/build-log/2026-08-21-sdd-ledger.md` and every `task-N-report.md` → `docs/build-log/reports/` (verbatim; these are the exact commands + outputs that proved each step). Do NOT copy the `review-*.diff` packages or brief files (briefs duplicate the plan).

- [ ] **Step 7: README "Documentation map" + cross-check**

Add to the root `README.md` a short section linking `CLAUDE.md` and each `docs/*.md`. Then verify every relative link in the new docs resolves (`grep -o '](\([^)]*\.md[^)]*\))' …` and test each path exists), verify every family-table cell against the code with grep (e.g. `grep -l jsonrpc v*/pentaho_reports/controllers/main.py` must list only v19; `grep -L ondelete v*/pentaho_reports/models/ir_actions_report.py` must list v11–v13; `ls v*/pentaho_reports/static/src/js/` shows `action_manager.js` for 11–14 and `action_service.js` for 15–19), and record the checks in the report.

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md README.md docs && git commit -m "docs: make the repo self-documenting (CLAUDE.md, architecture, add-a-version playbook, decisions, lessons, history, build log)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019Y7zs91xCuDwsyBGU5coZC"
```
