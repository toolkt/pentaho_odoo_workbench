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
