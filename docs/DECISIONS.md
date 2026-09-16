# Decision log

Format: **Decision** — Date — Context — Alternatives — Why — Cost if wrong.
Rulings made mid-build (from the SDD ledger, `build-log/2026-08-21-sdd-ledger.md`)
are entries like any other.

---

**Per-version FOLDERS, not Odoo.sh branches** — 2026-08-21 — nine Odoo versions must
be shippable from one repo — *Alternatives:* one branch per Odoo version (the
Odoo.sh convention) — *Why:* Odoo.sh only auto-loads modules at a repository's root;
clients copy `vNN/pentaho_reports` into their own repo anyway, and folders keep one
history, one CI, one diffable tree — *Cost if wrong:* a re-layout; no code changes.

**One canonical engine with nine REAL copies** — 2026-08-21 — the renderer must be
identical everywhere — *Alternatives:* symlinks; a pip package; per-version forks —
*Why:* Odoo module folders must be self-contained when copied out (symlinks break,
pip is unavailable on Odoo.sh); forks would drift instantly. Byte-identical copies +
`tools/sync_native.py` + `tools/check_drift.py` (and a pytest) give self-containment
AND drift protection — *Cost if wrong:* sync friction only.

**Python floor 3.6, not 3.5, not 3.7+** — 2026-08-21 — Odoo 11's local venv runs
3.6.8; the engine used 3.7 features (`dataclasses`, postponed annotations) —
*Alternatives:* 3.5 (the `odoo:11` Docker image); keep 3.7 and drop v11 — *Why:* the
actual deployment target is the 3.6.8 venv; 3.5 would forbid f-strings for marginal
benefit. Port = plain `_Record` classes + `typing.Optional/List/Dict` — *Cost if
wrong:* an informed exclusion documented in `engine/native/COMPAT.md`.

**Throwaway DBs `pentaho_test_vNN` as acceptance** — 2026-08-21 — proving "installs
on Odoo NN" needs a real install — *Alternatives:* mock-level tests only — *Why:*
the failure modes that matter (asset bundles, route types, ORM decorators) only
surface in a real `odoo-bin -i … --test-enable`; DBs are created `createdb -O odooNN`
and always dropped — *Cost if wrong:* slower acceptance runs.

**`engine/native/` keeps the import name `native`** — 2026-08-21 — the module
imports `from .native…`/`native.*` — *Why:* the synced copy sits at
`vNN/pentaho_reports/native/`, so keeping the package name makes canonical and copy
import-identical; tests run unchanged in both places — *Cost if wrong:* renames.

**Vendored, credential-scrubbed fixtures** — 2026-08-21 — the committed engine tests
referenced `.prpt` files OUTSIDE the repo (26/91 errored), and the real files embed
client JDBC credentials — *Why:* tests must be self-contained; `tools/scrub_fixture.py`
rewrites user→`demo`, password→empty, url→`jdbc:postgresql://localhost/demo`, and
`test_fixtures_scrubbed.py` enforces it forever. The renderer never reads the JDBC
block, so scrubbing changes nothing functionally — *Cost if wrong:* none.

**Synthetic `partner_list.prpt` instead of Piaggio-bound module tests** — 2026-08-21
— the old Odoo-side tests needed a specific client DB — *Why:* a fixture whose query
targets `res_partner` runs on any fresh Odoo DB, so one version-agnostic test suite
serves all nine folders — *Cost if wrong:* one derived fixture to maintain.

**Version-agnostic module tests** — 2026-08-21 — nine copies of tests would drift —
*Why:* single test design with capability detection: `tagged` fallback (11),
`group_ids`/`groups_id` (19), JSON via `self.opener` (16+ test mode), dispatch-shape
detection — the same files pass 11→19 — *Cost if wrong:* slightly denser tests.

**JS resolves reports by `report_name`** — 2026-08-21 — the action payload differs
across versions — *Why:* `report_name` is present and stable in the action on every
version; ids are not — *Cost if wrong:* an extra RPC.

**Per-version dispatch aliases over one shared name** — 2026-08-21 — Odoo's generic
report machinery calls `render_<type>` (11–13), `_render_<type>(res_ids)` (14–15),
`_render_<type>(report_ref, res_ids)` (16+) — *Why:* meet each version's contract
exactly and funnel into the shared `_render_pentaho_report` — *Cost if wrong:* the
dispatch test fails loudly.

**Keep the `fileToken` cookie contract** — 2026-08-21 — legacy `session.get_file`
(the v11 path) polls a `fileToken` cookie to unblock the UI — *Why:* without it the
UI blocks forever on v11; harmless elsewhere — *Cost if wrong:* stuck spinners.

**v19 route `type='jsonrpc'`** — 2026-08-21 — Odoo 19 renamed the JSON route type,
keeping `'json'` only as a deprecation alias — *Why:* write the real name where it
exists; 17–18 keep `'json'` — *Cost if wrong:* deprecation warnings.

**Harness shims instead of venv mutations** — 2026-08-21/23 — several local venvs
fight the harness — *Decisions:* `--limit-memory-hard=0` on Darwin for N<16 (Odoo
≤15 calls `setrlimit(RLIMIT_RSS)`, EINVAL on macOS); `tools/pil_compat/
sitecustomize.py` via PYTHONPATH for N≤12 (Pillow ≥10 removed `Image.ANTIALIAS`,
Odoo ≤12 core needs it); `pytest.ini` testpaths (duplicate test basenames across
synced copies break bare pytest) — *Why:* the user's venvs are production tooling;
the harness adapts, not the environment — *Cost if wrong:* harness-only quirks.
**The single sanctioned venv change:** `odoo14/venv` gets `reportlab==3.5.55` — that
venv shipped broken (no reportlab at all), so this is a repair, not a preference.

**`.catch` instead of `guardedCatch` on 13–14** — 2026-08-21 (Task 9 review ruling)
— `guardedCatch` skips rejections whose reason is an `Error` instance, so a thrown
error never unblocked the UI — *Why:* `.catch` + an `errorMessage()` helper handles
every shape — *Cost if wrong:* none (the file is the family reference).

**`errorMessage()` + `event.preventDefault()` on 11–12** — 2026-08-21 (Task 9/10
rulings) — `_rpc` rejects with `(error, $.Event())` on 11–12 and `{message, event}`
on 13+; without `preventDefault` Odoo also shows its own crash dialog on top of our
notification, and jQuery 1.11 Deferreds neither assimilate native Promises nor catch
thrown errors — *Cost if wrong:* double dialogs, "[object Object]" toasts.

**Two v11-only test shims** — 2026-08-21 (Task 11 review ruling, verified against
Odoo 11 source) — (a) the `tagged` fallback sets `post_install`/`at_install` class
attrs because Odoo 11's at-install slot is demo-gated and the harness runs
`--without-demo=all`; (b) a real `self.cr.commit()` in the user fixture because
Odoo 11's `HttpCase.authenticate` reads through a second cursor that cannot see
uncommitted rows — *Why:* both are contracts of Odoo 11 itself; the DB is
disposable — *Cost if wrong:* v11 test isolation only (users leak per run; logins
are unique per run).

**Doc sweep routed to Task 12** — 2026-08-21 (Task 10 review ruling) — the manifest/
index.html Python-API example named `_render_pentaho(report.id, ids, {...})` — wrong
name on 11–13 and wrong arity everywhere — *Why:* fix once across all nine folders by
pointing the example at `render_report(report.id, ids, data)` (same contract on every
version) — *Cost if wrong:* a doc example only. Done in Task 12 (2026-08-23).

**Task 13 added; Task 12 commits without pushing** — 2026-08-21 (user request) —
the repo must be self-documenting (this file is part of that), and branch
integration happens once at the end via the finishing-a-development-branch flow —
*Cost if wrong:* documentation debt only.

---

## 2026-09-17 — Java-server parity (NextAsia Land benchmark)

Evidence: `build-log/reports/2026-09-17-nextasia-java-parity.md`.

**The Java server's real output is the fidelity reference** — 2026-09-17 — NextAsia
Land compared every report printed by `tk_pentaho_v18` (Tomcat Java server) with the
native engine on Odoo.sh — *Alternatives:* keep calibrating against a Report Designer
render on a workstation — *Why:* that's what clients compare against; 17 reports ×
22 records were rendered by both engines from the same database and diffed (pages,
text, ink overlap) — *Cost if wrong:* nothing irreversible; the calibration tests
keep their Java-measured geometry.

**Arial → base-14 Helvetica (no TTF embedding)** — 2026-09-17 — the Java server on
Linux has no Arial and writes non-embedded Helvetica; the engine embedded whatever
TTF the host had (Liberation Sans on Odoo.sh, Arial on macOS), so glyphs and widths
changed per host — *Alternatives:* bundle a TTF in the module — *Why:* Helvetica is
what the reference prints, every PDF viewer has it, and the output is identical on
every host; Arial and Helvetica share advance widths, so the Java wrap-count
calibration still passes (that test is no longer skipped) — *Cost if wrong:* a
client whose Java server had real Arial sees Helvetica glyphs (same metrics).

**Sub-report `<parameter-mapping>` input parameters** — 2026-09-17 — the engine ran
every sub-report with the master's top-level parameters (AP Voucher `KeyError: 'id'`;
multi-record PRS printed all records' lines) — *Why:* `name → alias` copies the master
row field (else master parameter) per master row; `name="*"` imports all; an unknown
source arrives as NULL, as in Java; the master's reserved parameters stay visible so
bundles without a mapping behave as before; the rows cache is keyed by bundle +
bound parameters — *Cost if wrong:* a mapped sub-report query sees different values.

**An unplaced sub-report is placed by its root style x AND y** — 2026-09-17 — the
engine only took the root x ("Java ignores root y") — *Why:* that holds when the
`<sub-report>` element has its own `spatial-styles`; without them Java uses the
sub-report's root layout x and y (PRS signature sub-report `y=12`) — *Cost if
wrong:* a sub-report shifted by its root y.

**A formula subset, not a formula engine** — 2026-09-17 — style expressions were
ignored; the reports use only `IF(ISBLANK([f]); …)` and `IF([f]=""; …)` for
`visible`/`border-*-style` — *Alternatives:* a full LibreFormula implementation —
*Why:* a ~120-line evaluator covers the real usage; `ISBLANK` is NULL-only as in
Pentaho (`''` is not blank); unsupported formulas raise `FormulaError` and the static
style stands — *Cost if wrong:* a report relying on another function keeps its static
style, as before.

**`details-header`/`details-footer` emitted only when they have elements** —
2026-09-17 — these bands were skipped entirely ("Nothing Follows", grand totals) —
*Why:* emitting empty bands would change the recorded band sequence of every existing
report (and the nested-group emission tests); non-empty ones print once per leaf
partition around its rows, and around a sub-report's rows — *Cost if wrong:* none
observed.

**NUMERIC stays `Decimal` in report queries** — 2026-09-17 — Odoo registers a
global NUMERIC→float cast (`sql_db.undecimalize`), so a `numeric(…,2)` text-field
printed `30.0` where Java (BigDecimal) prints `30.00` — *Alternatives:* registering
the Decimal cast on Odoo's own cursor (leaks Decimals into the ORM for the rest of
the request); a new registry cursor (loses the request's transaction) — *Why:* a side
psycopg2 cursor of the same connection shares the transaction and snapshot, and a
cursor-scoped `register_type` affects nothing else; `TestCursor` (12+) is unwrapped
via `_cursor`, and without a connection the plain cursor path is kept — *Cost if
wrong:* floats again (the previous behavior), never a crash.
