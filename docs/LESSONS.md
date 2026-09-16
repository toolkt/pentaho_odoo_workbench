# Lessons — gotchas discovered while building

Each: **symptom → cause → fix → where it lives**.

- **Odoo ≤12 crashes on image fields in a fresh DB** → Pillow ≥ 10 removed
  `Image.ANTIALIAS` and Odoo ≤12 core still references it (the local odoo12 venv has
  Pillow 11.3) → a harness-only `sitecustomize.py` restores the alias via PYTHONPATH,
  never touching the venv → `tools/pil_compat/sitecustomize.py`, wired in
  `tools/odoo_install_test.sh` for N ≤ 12.

- **Odoo ≤15 dies at boot on macOS** → `setrlimit(RLIMIT_RSS)` returns EINVAL on
  Darwin → pass `--limit-memory-hard=0` for N < 16 on Darwin →
  `tools/odoo_install_test.sh`.

- **bash script aborts with "unbound variable" on an empty array** → macOS ships
  bash 3.2, where `"${arr[@]}"` under `set -u` errors when empty → the
  `${arr[@]+"${arr[@]}"}` idiom → all `tools/*.sh`.

- **Odoo 13/14 UI never unblocks after a render error** → `guardedCatch` skips
  rejections whose reason is an `Error` instance → use `.catch` with an
  `errorMessage()` normalizer → `v13/v14 …/static/src/js/action_manager.js`.

- **"[object Object]" notifications + a second crash dialog on 11–12** → `_rpc`
  rejects with `(error, $.Event())` on 11–12 (vs `{message, event}` on 13+), and
  without `event.preventDefault()` Odoo's own crash handler also fires → per-family
  fail handlers + `preventDefault` → `v11/v12 …/action_manager.js`.

- **jQuery 1.11 Deferreds are not Promises** → they don't assimilate native
  Promises, have no `.catch`, and errors *thrown* in callbacks are simply uncaught →
  v11/v12 JS stays in Deferred idiom end to end → `v11/v12 …/action_manager.js`.

- **HttpCase JSON posts 400 on Odoo 16+** → test mode rejects requests lacking the
  test-request-key cookie → post through `self.opener`, never a bare
  `requests.Session` → every `vNN/…/tests/test_controllers.py` (16+ effective).

- **Odoo's `--logfile` appends across runs** → stale failures from a previous run
  show up in the scan → the harness truncates the logfile before each run →
  `tools/odoo_install_test.sh`.

- **py3.6 venv ends up with corrupted Pillow dylibs** → upgrading the bootstrap pip
  and installing packages in the SAME invocation corrupts wheels being unpacked →
  split `pip install --upgrade pip` from the package install →
  `tools/engine_matrix.sh`.

- **reportlab 3.5.55 fails to build on current Clang** → implicit-function-
  declaration is an error now → `CFLAGS=-Wno-error=implicit-function-declaration`
  for that one pin (odoo14 venv repair) → task 9 report, `build-log/reports/`.

- **Odoo 19 renamed things** → `res.users.groups_id` → `group_ids`; JSON route
  `type='json'` is only a deprecation alias of `'jsonrpc'` → detection in the shared
  tests; real name in v19's controller → `v19/…`, `tests/test_controllers.py`.

- **`_('msg %s', x)` raises on Odoo 11–13** → `_()` is single-argument there →
  always `_('msg %s') % x` → all model/controller code, all versions.

- **`selection_add` without `ondelete` warns/fails from Odoo 14** → required 14+,
  invalid earlier → present in v14–v19, absent in v11–v13 → `models/ir_actions_report.py`.

- **View syntax is a hard fence at 17** → `attrs=` rejected from 17; python-expression
  attributes rejected before 17 → two view files families →
  `vNN/…/views/report_views.xml`.

- **Real `.prpt` files embed client DB credentials** → Pentaho Report Designer
  writes the JDBC connection (including `encrypted:` password blobs) into
  `datasources/sql-ds.xml` → scrub before committing; a test enforces it →
  `tools/scrub_fixture.py`, `engine/native/tests/test_fixtures_scrubbed.py`.

- **Bare `pytest` at the repo root exploded** → nine synced copies mean duplicate
  test basenames, which pytest's default collection can't handle → `pytest.ini`
  pins testpaths to the canonical suite → `pytest.ini`.

- **Engine tests errored outside this machine** → fixtures lived outside the repo →
  vendored fixtures + a conftest whose `_FixturePath.read_bytes()` SKIPS when a
  fixture is absent (never FileNotFoundError) → `engine/native/tests/conftest.py`.

- **`from __future__ import annotations` hides 3.10-only syntax** → postponed
  evaluation means `X | None` in annotations imports fine on 3.7–3.9 and then the
  file fails on 3.6 anyway — and without the import the same syntax fails everywhere
  below 3.10 → the floor is enforced by *compiling* with py3.6, not by review →
  `engine/native/COMPAT.md`, `tools/test_matrix.sh` step 2.

- **Odoo 11 at-install tests silently run zero tests** → the at-install slot is
  demo-gated and the harness uses `--without-demo=all` → the `tagged` fallback sets
  `post_install`/`at_install` class attrs so the suite lands in the post-install
  slot → `v11/…/tests/__init__.py` (+ DECISIONS.md entry).

- **Odoo 11 `HttpCase.authenticate` can't see the test's users** → it reads through
  a second cursor; two open cursors are mutually invisible at READ COMMITTED → a
  real `self.cr.commit()` in the user fixture; safe only because the DB is
  throwaway; committed users outlive the test, so logins are unique per run →
  `v11/…/tests/test_controllers.py`.

## 2026-09-17 — Java-server parity (NextAsia Land)

- **Line items print on top of each other** → the details band has no height of its
  own; every cell is `min-height="100%"` + `dynamic-height="true"`, and a percentage
  height counted as 0 → a dynamic percentage-height text cell contributes its
  measured text height → `renderer._element_height`.

- **"Nothing Follows", GRAND TOTAL, "Received By" missing** → `details-footer` (and
  `details-header`) were skipped, and Report Designer writes their elements directly
  under the section tag (no `<root-level-content>`) → `bundle._section_band` +
  `Group.details_header/details_footer`.

- **Delivery Receipt shows only its header** → the whole line grid and signature block
  live in the `<watermark>` band (styles.xml), which was parsed but never painted →
  paint the watermark first on every page, taking no flow space → `_Flow._start_page`.

- **Empty report downloads as a broken PDF** → reportlab drops a page nothing was
  drawn on, producing a 0-page PDF; Java returns one blank page → `showPage()` when
  page 1 is empty → `NativeRenderer.render`.

- **Serif text where Java prints Arial; different glyphs on Odoo.sh** → text styles
  weren't inherited from the enclosing band (unset face → Serif), and Arial resolved
  to whatever TTF the host had → band→element text-style inheritance
  (`bundle._inherit_text_styles`) + base-14 Helvetica (`fonts.resolve`).

- **Quantities print `2` / `30.0` instead of `2.00`** → text-fields went through the
  number-field default format, and Odoo's cursor casts NUMERIC to float → Java
  `String.valueOf` semantics for text-fields (`formats.format_text_value`) + a
  Decimal side cursor in the glue (`_pentaho_execute_query`). Benchmarks that query
  with raw psycopg2 see Decimals and hide the Odoo half — render through Odoo too.

- **Same report, different line order on two copies of one database** → the report
  SQL has no `ORDER BY`, so rows come out in physical order, which a dump/restore
  changes → not an engine bug: add `ORDER BY` to the `.prpt` query (Odoo's `_order`
  for the line model), and bump the client module version so its report XML
  (`pentaho_load_file`) reloads the file.

- **Grep says Odoo 19 has no `cursor._cnx`** → it's annotated
  (`self._cnx: PsycoConnection = …`) → grep `self._cnx` without `=`.

- **`tools/odoo_install_test.sh`: `createdb: command not found`** → Postgres.app's
  client tools aren't on a non-login shell's PATH → prefix
  `/Applications/Postgres.app/Contents/Versions/latest/bin` before running
  `tools/test_matrix.sh`.
