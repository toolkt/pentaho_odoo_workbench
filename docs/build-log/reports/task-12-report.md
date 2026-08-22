# Task 12 report — test_matrix.sh, root README, full matrix run

Base: bb746a8 → commit 71b8278. Implementer: sonnet (dispatched 2026-08-21, in-flight
doc sweep) + Fable 5 (resumed 2026-08-23: verification, matrix run, commit).

## What was done
- `tools/test_matrix.sh` written per plan (drift → compileall per venv + engine@py3.6
  → engine_matrix → odoo_install_test 11..19; final table; exit non-zero on any FAIL).
- Root `README.md` replaced per plan Step 2 (version matrix, install incl. Odoo.sh
  note, repo organisation, verification, contributing).
- Task-10-ruling doc sweep across ALL NINE folders: manifest + static/description/
  index.html Python-API example now uses `render_report(report.id, ids, data)`
  (correct name + arity everywhere; returns (content_b64, output_type, filename,
  direct_print)); v11–13 model docstrings name their real dispatch alias
  (`render_pentaho`); v12 JS header no longer claims cookie polling (XHR onloadend);
  v11 JS header names `report.report` (not "ReportActionManager"); v11
  `cr.commit()` consequence comment added (leaked users persist; why rebinding
  self.cr fails).

## Evidence
```
### full acceptance run (tools/test_matrix.sh), 2026-08-23
  drift                            PASS
  compile engine@py3.6             PASS
  compile v11 .. v19               PASS (9 rows)
  engine matrix                    PASS
  odoo v11 .. v19 install+tests    PASS (9 rows)
  → 21/21 PASS, exit 0
```
- `psql -tAc "select datname from pg_database where datname like 'pentaho_test_%'"` → 0 rows.
- Working tree clean after commit 71b8278.
