# History

## Timeline

- **Origins** — clients' Pentaho `.prpt` reports ran through willowit's
  `Pentaho-reports-for-OpenERP`: an Odoo module delegating to the real Pentaho
  Reporting Classic engine on a Java report server. Functional, but a hard external
  dependency — and impossible on Odoo.sh.
- **2026-08-12 — the pure-Python fidelity port** (`PORT_CHANGES.md`): the renderer
  was rebuilt in pure Python against the Java engine as the fidelity reference,
  measured by rendering all 1,639 real client reports: RENDER-OK went from
  1435/1639 to **1582/1639 (~96.5%)**, and parse-OK == render-OK (no silent parse
  successes that fail to render). The remaining ~3.5% are a documented long tail
  (crosstabs, style-expression formulas, list-parameters, corrupt zips).
- **2026-08-21 — the per-version layout** (this repo's shape): design in
  `superpowers/specs/2026-08-21-per-version-layout-design.md`, a 13-task plan in
  `superpowers/plans/2026-08-21-per-version-layout.md`, and a **9-agent source
  survey** of the local Odoo 11–19 trees producing
  `superpowers/specs/2026-08-21-odoo-version-api-survey.md` (per-version API facts
  with file:line evidence — the document every glue decision cites).
- **2026-08-21 → 2026-08-23 — the build**: subagent-driven development, one
  implementer + one reviewer per task, every task's evidence preserved (see
  `build-log/`). Engine ported to the 3.6 floor; fixtures vendored and scrubbed;
  v19 built as the family-C reference with universal tests and the install harness;
  then v18/v17, v16/v15, v14 (family-A reference), v13/v12, v11; finally the
  acceptance matrix: **21/21 PASS** (drift, compileall per venv, engine matrix,
  nine real Odoo installs).

- **2026-09-17 — Java-server parity** (NextAsia Land, `build-log/reports/2026-09-17-nextasia-java-parity.md`):
  the Odoo 18 copy was deployed to Odoo.sh and benchmarked against the client's
  production Java server on the same database — 17 reports, 22 records, pages/text/
  ink diffed. The fixes (sub-report parameter mapping, percentage-height rows,
  details header/footer, watermark, empty report page, visibility, text-style
  inheritance, base-14 fonts, text-field numbers, inline/row band layouts, unplaced
  sub-report placement, style-expression formulas, NUMERIC scale) brought every case
  to 100% text parity; they were handed back here to engine + all nine glue folders.
  Corpus render-OK unchanged at 1582/1639; acceptance matrix re-run.

## How it was built

Brainstorm → spec → plan → task-by-task execution with an independent review per
task. Reviews produced rulings (recorded in the ledger and expanded in
`DECISIONS.md`); several became repo policy (harness shims over venv mutations,
`.catch` over `guardedCatch`, the Task 12 doc sweep). The 9-agent survey of the
actual local Odoo trees — not the documentation — is why the family tables cite
file:line evidence rather than folklore.

## Where the evidence lives

- `build-log/2026-08-21-sdd-ledger.md` — the verbatim execution ledger: every task's
  dispatch, review verdict, rulings, and fix rounds.
- `build-log/reports/task-N-report.md` — each task's exact commands and outputs.
- Branch: `feat/odoo-11-19-layout`, commits `ee2e240` (gitignore) through the
  acceptance-matrix commit — `git log --oneline --reverse` reads as the build story.
