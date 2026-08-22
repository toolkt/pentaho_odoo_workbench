# Task 13 report — self-documenting repository

Base: 71b8278. Implementer: Fable 5 (2026-08-23).

## Files created
CLAUDE.md (agent entry point, ≤150 lines, family table inline);
docs/ARCHITECTURE.md (intention, component map, definitive grep-verified family
table, print data flow, test strategy, environment matrix, limits);
docs/ADDING-A-VERSION.md (v20 playbook: survey questionnaire + grep starting points,
sibling copy, decision checklist, tooling wiring, proof commands, worked v18→v19 and
v14→v15 diffs); docs/DECISIONS.md (all design decisions + every ledger Ruling as a
full entry with cost-if-wrong); docs/LESSONS.md (19 gotchas, symptom→cause→fix→where);
docs/HISTORY.md (timeline: willowit Java origins → 2026-08-12 fidelity port →
2026-08-21 layout → 2026-08-23 21/21 matrix); docs/build-log/README.md + verbatim
copies of the SDD ledger and task-1..13 reports. README gained a Documentation map.

## Verification (recorded per plan Step 7)
- Link check: every `](*.md)` relative link in the new docs resolves. 0 broken.
- Family-table facts re-verified against the code:
  `grep -l jsonrpc v*/pentaho_reports/controllers/main.py` → v19 only;
  `grep -L ondelete v*/pentaho_reports/models/ir_actions_report.py` → v11 v12 v13;
  `ls v*/pentaho_reports/static/src/js/` → action_manager.js on 11–14,
  action_service.js on 15–19; v11 create is `@api.model` (no model_create_multi);
  index.html Python-API example uses `render_report`.
