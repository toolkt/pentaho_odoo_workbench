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

## Documentation map

- [`CLAUDE.md`](CLAUDE.md) — the working agreement for this repo (rules, families table, verify/change recipes); loaded automatically by Claude Code.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — intention, component map, the definitive three-family table, print data flow, test strategy, environment matrix, known limits.
- [`docs/ADDING-A-VERSION.md`](docs/ADDING-A-VERSION.md) — the v20 playbook: survey questionnaire, sibling copy, decision checklist, tooling wiring, proof.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — every decision with context, alternatives, why, and cost-if-wrong (including mid-build review rulings).
- [`docs/LESSONS.md`](docs/LESSONS.md) — gotchas: symptom → cause → fix → where it lives.
- [`docs/HISTORY.md`](docs/HISTORY.md) — timeline from the Java-server origins through the fidelity port to this layout.
- [`docs/PORT_CHANGES.md`](docs/PORT_CHANGES.md) — the 2026-08-12 pure-Python fidelity port (1582/1639 real reports render).
- [`docs/build-log/`](docs/build-log/README.md) — the verbatim build ledger and per-task evidence reports.
- [`engine/native/COMPAT.md`](engine/native/COMPAT.md) — the Python 3.6 floor rule.
