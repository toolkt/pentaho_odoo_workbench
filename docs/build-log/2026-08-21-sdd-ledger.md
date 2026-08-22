# SDD ledger — plan: docs/superpowers/plans/2026-08-21-per-version-layout.md
Spec: docs/superpowers/specs/2026-08-21-per-version-layout-design.md (authority). Branch: feat/odoo-11-19-layout (from main @ e732800).

## Pre-flight conflict scan (2026-08-21)

| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1 sync/drift ↔ T5 partner_list | T1 sync copies fixtures/partner_list.prpt if present; T5 creates it; drift checks it only if present | consistent |
| T1 ↔ T2 conftest | T1 moves native/ to engine/native; T2 conftest computes PACKAGE_PARENT = parents[1] of tests/ → engine/ (canonical) or pentaho_reports/ (copy) | consistent |
| T2 scrub tool ↔ T5 fixture generation | T2 `scrub(src,dest,query,label)`; T5 calls CLI `--query --label` | consistent |
| T2 test_fixtures_scrubbed EXPECTED (8) ↔ T5 adds partner_list | partner_list not in EXPECTED set; test_all_expected uses `<=` so extra file OK; test_fixture_has_no_credentials parametrized over EXPECTED only — partner_list is derived from a scrubbed source so also clean | consistent |
| T3 `_Record` ↔ bundle.py construction | bundle.py constructs BorderSide(width=, style=), Element(kind=...), Style(...) by keyword; `_Record` supports kwargs + positional | consistent (positional `BorderSide(w, s)` also supported) |
| T4 engine_matrix ↔ T3 py36 venv name | both use `py36-rl3559` under scratchpad/venvs → T4 reuses T3's venv | consistent |
| T6 tests ↔ T6 model | tests call `render_report(report_id, res_ids, data)`, `_render_pentaho_report(res_ids, data)`, dispatch check for `_render`/`render` | consistent with T6/T8/T10/T11 hooks |
| T6 harness ↔ T7–T12 | `tools/odoo_install_test.sh NN` used identically | consistent |
| T6 test_controllers `_url` ↔ harness `--http-port` | config['http_port'] exists on 11 (verified `tests/common.py:48`) | consistent |
| T7 copies v19 (jsonrpc→json) → T8 copies v17 → T9 copies v15 → T10 copies v14 → T11 copies v12 | each copy chain inherits the right prior edits (attrs views from T8 reach 14–11; legacy JS from T9 reaches 13–11; v12 deferred JS reaches 11) | consistent |
| T8 v15 dispatch (`_render_pentaho(res_ids)`) → T9 v14 inherits | T9 Step 6 verifies | consistent |
| T10 v13/12 `render_pentaho` → T11 v11 inherits | correct for 11 | consistent |
| Global constraint "no `X | None`" ↔ T3 code | T3 uses Optional[...] | consistent |
| Rubric: tests asserting nothing? | T6 `test_download_requires_login` asserts status in a tuple incl. 404 — weak but real (auth redirect) | accept |
| Rubric: duplication | nine glue copies are plan-mandated (spec §2 "real copies, not symlinks") | Ruling: accept duplication of glue + native across vNN — spec-mandated; cost if wrong: maintenance burden already accepted by user |
| Push in T12 Step 5 | pushes to shared `main` | Ruling: work happens on branch feat/odoo-11-19-layout; T12's `git push origin main` is NOT executed by the implementer — the branch is finished via finishing-a-development-branch with the user's choice. Cost if wrong: one extra manual step |

Task 1: dispatched (BASE ee2e240, implementer sonnet)
Task 1: review (sonnet) spec ✅; Important: duplicate test basenames break multi-dir pytest collection → fix round 1 (root pytest.ini testpaths + chmod +x tools). Minor (deferred): report said 8 test files, actually 9.
Task 1: fix round 1/5 (2 addressed, 0 open — pytest.ini testpaths; chmod +x tools; commits b145ab1..0b442c2)
Task 1: complete (commits ee2e240..0b442c2, review clean)
Task 2: dispatched (BASE 0b442c2, implementer sonnet)
Task 2: review (sonnet) spec ✅, quality Approved. Minor (deferred): conftest `MODULE_DIR` alias unused; `import pytest` unused in test_preview_render.py; test_bundle.py:230 comment still says piaggio_reports/. Note: pytest "1 warning" is reportlab's own ast.NameConstant DeprecationWarning (third-party, py3.12) — not ours.
Task 2: complete (commits 0b442c2..6e8a79e, review clean)
Task 3: dispatched (BASE 6e8a79e, implementer sonnet)
Task 3: review (opus) spec ✅, quality Approved. Important (plan-mandated) "COMPAT.md:17 names tools/test_matrix.sh which no task creates" — Ruling: reviewer only saw briefs 1–6; plan Task 12 creates tools/test_matrix.sh, so the COMPAT.md text is correct and stands — cost if wrong: one stale doc line. Minor (deferred): renderer.py:297 type comment has trailing prose (invalid PEP 484 comment); model.py:3 unused Dict/List/Optional imports; BorderSide field comment on wrong line; `__ne__` redundant; no recursion guard in __repr__; _required not cross-checked vs _fields. Implementer deviation accepted: tests/calibration.py also converted (required for 3.6 collection).
Task 3: complete (commits 6e8a79e..6b7bd6b, review clean)
Task 4: dispatched (BASE 6b7bd6b, implementer sonnet)
Task 4: review (sonnet) ❌ quality: Critical false-PASS on venv reuse after PIP-FAIL; Important negative-only classification, tail-1 discards diagnostics, no pipefail. All plan-mandated (script verbatim from brief) — Ruling: fix them; the matrix is the project's acceptance criterion (spec §7) and a false PASS defeats it — cost if wrong: none beyond a slightly longer script. → fix round 1 (sentinel .ready, rm venv on fail, positive-signal grep, full log file, pipefail, negative test).
Task 4: fix round 1/5 (4 addressed, 0 open — .ready sentinel + rm on fail, positive-signal grep, full log, pipefail; plus split pip self-upgrade (py3.6 bootstrap pip corrupts Pillow dylibs when combined) and dropped redundant pip<22; commits 503227b..77efb21). Minor (deferred): reuse keyed on label only — a changed pin under the same label reuses a stale venv.
Task 4: complete (commits 6b7bd6b..77efb21, review clean)
Task 5: dispatched (BASE 77efb21, implementer sonnet)
Task 5: review (sonnet) spec ✅, Approved, no issues.
Task 5: complete (commits 77efb21..733badc, review clean)
Task 6: dispatched (BASE 733badc, implementer sonnet)
Task 6: review (opus) spec ✅ Approved; Important#1 bash-3.2 empty-array abort in harness (plan-mandated) → fix round 1; Important#2 dispatch test needs 11–15 hooks — Ruling: already mandated by plan Task 8 Step 4 (`_render_pentaho(res_ids)` for v15/v14) and Task 10 Step 2 (`render_pentaho` for v13/v12/v11); no change in Task 6 — cost if wrong: Task 8/10 harness runs fail loudly. Implementer deviations accepted: login test clears self.opener cookies (bare requests.Session is 400'd by 16+ test mode; 400 not in accepted set so no masking); harness truncates logfile (Odoo appends). Minor (deferred): harness `odoo.sql_db ERROR` pattern could false-FAIL on a caught bad query; `grep -v test-tags` could swallow a real error line; test_render.py:4 docstring names nonexistent helpers; login test accepts 404.
Task 6: fix round 1/5 (3 addressed, 0 open — bash-3.2 array guard, comment/docstring accuracy; commits 74054ba..09d6788)
Task 6: complete (commits 733badc..09d6788, review clean)
Task 7: dispatched (BASE 09d6788, implementer sonnet)
Task 7: review (sonnet) spec ✅ Approved, no issues.
Task 7: complete (commits 09d6788..3b86956, review clean)
Task 8: dispatched (BASE 3b86956, implementer sonnet)
Task 8: review (sonnet) spec ✅ Approved, no issues. Harness gained --limit-memory-hard=0 on Darwin for N<16 (Odoo ≤15 RLIMIT_RSS EINVAL on macOS); 17–19 re-proven.
Task 8: complete (commits 3b86956..267f9b2, review clean)
Task 9: dispatched (BASE 267f9b2, implementer sonnet)
Task 9: review (opus) spec ✅ but quality Needs fixes: Important#1 guardedCatch skips Error rejections → never-unblock (plan-mandated); Important#2 _rpc rejection shape → "[object Object]" notification + core crash dialog not prevented (plan-mandated). Ruling: fix both now — the file is the reference copied into v13/v12/v11 — cost if wrong: none. → fix round 1 (.catch, errorMessage() helper, event.preventDefault, header comment). Minor (deferred): dead `if (!ok)` on 13/14; printWithPrintJS has no timeout failsafe (Safari lands there); unused isChrome/isEdge/isSafari; filename strip duplicates server side.
Task 9: fix round 1/5 (3 addressed, 0 open — .catch, errorMessage(), preventDefault, header comment; commits 86ffb3f..2811238)
Task 9: complete (commits 267f9b2..2811238, review clean)
Task 10: dispatched (BASE 2811238, implementer sonnet) — carries ruling: v12 JS must include errorMessage() + (error, event) fail handler with event.preventDefault (Odoo 11/12 _rpc rejects with (error, $.Event()); verified ajax.js:74,91-94)
Task 10: implementer DONE_WITH_CONCERNS (b339cbf): v13 PASS, v12 PASS only via out-of-repo PYTHONPATH sitecustomize shim (local odoo12 venv has Pillow 11.3; Odoo 12 core needs Image.ANTIALIAS, removed in Pillow 10 → fresh-DB bootstrap of `base` fails, unrelated to our module). Ruling: bake the shim into the repo harness (tools/pil_compat/sitecustomize.py via PYTHONPATH for N<=12) rather than mutate the user's venv — cost if wrong: a harness-only shim that never affects production installs. Pre-review fix requested.
Task 10: review (opus) spec ✅ Approved. Important (plan-mandated, cross-version): manifest description + static/description/index.html Python-API example names `_render_pentaho(report.id, ids, {...})` — wrong name on 11–13 and wrong arity everywhere since the refactor. Ruling: fix in Task 12's doc sweep across ALL nine folders by pointing the example at `render_report(report.id, ids, data)` (exists with the same contract on every version) — cost if wrong: a doc example only. Minor (deferred → Task 12 sweep): models/ir_actions_report.py:134 docstring says `_render_pentaho` in v11–13 (should be render_pentaho); v12 JS header claims cookie polling but Odoo 12's get_file is XHR/onloadend (cookie matters on 11 only); dead `var def` before guards in v12 JS; harness PYTHONPATH leading-colon when caller has PYTHONPATH and N≥13; shim shadows any venv sitecustomize.
Task 10: complete (commits 2811238..a932e6d, review clean)
Task 11: dispatched (BASE a932e6d, implementer sonnet)
Plan amended at user request: Task 13 self-documentation added; Task 12 no longer pushes (Ruling: integration via finishing-a-development-branch).
Task 11: implementer DONE_WITH_CONCERNS (bb746a8): v11 PASS 15/15 but two v11-only test shims: (a) `tagged` fallback sets post_install/at_install class attrs (Odoo 11 at-install tests are demo-gated; harness uses --without-demo=all, so a no-op fallback ran nothing); (b) `self.cr.commit()` in _make_user because Odoo 11 HttpCase.authenticate reads via two mutually-invisible cursors. Sent to review (opus) for verification before ruling.
Task 11: review (opus) spec ✅ Approved. Both v11 test shims independently verified against Odoo 11 source (loading.py:182-210 demo-gated at-install slot; module.py:478-492 runs_at; common.py:176-181/262-266/283-301 two-cursor authenticate; res_users.py:469). Ruling: accept both v11-only shims (tagged fallback sets post_install/at_install; real cr.commit() in _make_user, DB is disposable) — cost if wrong: v11 test isolation only. Minor (deferred → Task 12/13 sweep): add comment that leaked users persist + why rebinding self.cr fails; JS header still says "ReportActionManager" (Odoo 11 has report.report).
Task 11: complete (commits bd1ecf2..bb746a8, review clean)
Task 12: dispatched (BASE bb746a8, implementer sonnet)
Task 12: implementer resumed 2026-08-23 (session a7ae7ae6, Fable 5): in-flight doc sweep verified complete (render_report Python-API example across all nine manifests + index.html; v11-13 model docstrings; v11/v12 JS headers; v11 cr.commit consequence comment), root README per plan. Full matrix run: ALL 21 rows PASS (drift, compile engine@py3.6, compile v11..v19, engine matrix, odoo v11..v19 install+tests). No pentaho_test_* DBs left.
Task 12: complete (commit follows)
Task 13: implemented (Fable 5, 2026-08-23): CLAUDE.md + docs/{ARCHITECTURE,ADDING-A-VERSION,DECISIONS,LESSONS,HISTORY}.md + build-log (ledger + task-1..13 reports verbatim) + README documentation map. Link check 0 broken; family-table cells grep-verified (jsonrpc→v19 only; ondelete absent 11-13; action_manager 11-14 / action_service 15-19; v11 @api.model).
Task 13: complete (commit follows)
