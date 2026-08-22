# Task 4 Report: `tools/engine_matrix.sh` — engine tests across interpreter × reportlab pins

## What was implemented

Created `tools/engine_matrix.sh`, copied verbatim from the task brief (Step 1),
and made it executable (`chmod +x`). No modification to the script body was
needed or made — a `diff` against the brief's fenced code block shows the only
difference is the markdown closing fence line, confirming byte-for-byte match.

The script:
- Resolves `SCRATCH="${SCRATCH_VENVS:-<scratchpad>/venvs}"` (env-overridable,
  defaults to the session scratchpad `venvs/` dir named in the brief).
- Iterates six `label|interpreter|reportlab-pin|extra-pins` combos, creating
  each scratch venv on first use (`$venv/bin/python` missing) and reusing it
  otherwise.
- Installs `pip`, the extra pins, and the pinned `reportlab==X` into each new
  venv.
- Runs `pytest -q -p no:cacheprovider` from `engine/native/tests` under each
  venv's interpreter, capturing the last summary line.
- Classifies each combo PASS/FAIL by grepping the summary line for
  `failed`/`error`, builds a results table, and exits non-zero if any combo
  failed.

No changes were made under `engine/native/`.

## Run output (verbatim)

Ran from repo root (`pwd` confirmed: `/Volumes/Workspace/Development/Workbench/pentaho-report-designer/pentaho_odoo_workbench`, branch `feat/odoo-11-19-layout`) with no env overrides, so it used the default scratchpad `venvs/` dir, reusing the pre-existing `py36-rl3559` venv per the brief and creating the other five.

```
== py36-rl3559: python 3.6.8 reportlab 3.5.59
114 passed in 1.96s
== creating py39-rl3559 (/opt/homebrew/bin/python3.9, reportlab==3.5.59)
== py39-rl3559: python 3.9.24 reportlab 3.5.59
114 passed in 6.48s
== creating py39-rl4410 (/opt/homebrew/bin/python3.9, reportlab==4.4.10)
== py39-rl4410: python 3.9.24 reportlab 4.4.10
114 passed in 3.23s
== creating py39-rl500 (/opt/homebrew/bin/python3.9, reportlab==5.0.0)
== py39-rl500: python 3.9.24 reportlab 5.0.0
114 passed in 3.20s
== creating py310-rl368 (/opt/homebrew/bin/python3.10, reportlab==3.6.8)
== py310-rl368: python 3.10.19 reportlab 3.6.8
114 passed, 1 warning in 4.51s
== creating py312-rl410 (/opt/homebrew/bin/python3.12, reportlab==4.1.0)
== py312-rl410: python 3.12.12 reportlab 4.1.0
114 passed, 1 warning in 3.07s

engine matrix:
  py36-rl3559|PASS|114 passed in 1.96s
  py39-rl3559|PASS|114 passed in 6.48s
  py39-rl4410|PASS|114 passed in 3.23s
  py39-rl500|PASS|114 passed in 3.20s
  py310-rl368|PASS|114 passed, 1 warning in 4.51s
  py312-rl410|PASS|114 passed, 1 warning in 3.07s
```

Script exit code: `0` (confirmed via `EXIT:$?` capture immediately after the run).

## Per-combo python/reportlab versions (as printed by the script itself)

| label | python | reportlab | tests |
|---|---|---|---|
| py36-rl3559 | 3.6.8 | 3.5.59 | 114 passed |
| py39-rl3559 | 3.9.24 | 3.5.59 | 114 passed |
| py39-rl4410 | 3.9.24 | 4.4.10 | 114 passed |
| py39-rl500 | 3.9.24 | 5.0.0 | 114 passed |
| py310-rl368 | 3.10.19 | 3.6.8 | 114 passed, 1 warning |
| py312-rl410 | 3.12.12 | 4.1.0 | 114 passed, 1 warning |

All six combinations report **PASS**; no engine/reportlab incompatibilities
surfaced.

## pip issues

None. All six `reportlab` pins (3.5.59, 3.5.59, 4.4.10, 5.0.0, 3.6.8, 4.1.0)
installed cleanly with prebuilt wheels on their respective interpreters — no
build failures, no missing wheels. The `--only-binary=:all:` escape hatch
mentioned in the brief for the py3.6 combo was not needed (that venv was
reused as-is from Task 3/pre-existing setup and its test run succeeded
without any reinstall).

## Files changed

- Created: `tools/engine_matrix.sh` (mode 0755)
- No other files touched; nothing under `engine/native/` was modified.

Commit: `503227b` — "tools: engine test matrix across Python × reportlab pins"
(`git status --short` after commit is clean; `git show --stat` confirms only
`tools/engine_matrix.sh` was added, 40 insertions).

## Self-review

- Script matches the brief exactly — verified with `diff` against the brief's
  fenced block; only difference is the markdown closing fence, i.e. the
  script body is a verbatim copy.
- Exit code is 0 only when all combos pass — verified: `set -u`, `fail=0`
  initially, only flipped to 1 on `VENV-FAIL`/`PIP-FAIL`/pytest
  failed-or-error summary; this run's actual `$?` was `0`.
- Table is printed — the `engine matrix:` block with all six
  `label|PASS|<summary>` rows appears at the end of stdout.
- The pre-existing `py36-rl3559` venv was reused, not recreated — confirmed
  two ways: (1) no `== creating py36-rl3559 ...` line appears in the output
  (all five other combos show their `creating` line, py36 does not), and
  (2) `stat` on `py36-rl3559/bin/python3` shows its original creation
  timestamp (15:42) unchanged by this run (15:58–16:00).
- Ran every command from the repo root; confirmed via `pwd` before each
  Bash invocation. No `cd` into another repo/worktree, no writes into any
  Odoo venv.
- No reformatting of unrelated files; commit is a single clean addition.

## Concerns

None. All six combinations pass with 114 tests each (two of the newer-Python
combos additionally report 1 warning, non-fatal, not a failure).

---

## Fix Round 1 (post-review)

The review found a reproducible false-PASS defect in the brief's own script
(venv-reuse-after-failed-install) and required fixing it plus three related
hardening items. Applied all four, then discovered and fixed two *additional*
real bugs while executing the review's mandated "delete-and-rebuild" end-to-end
verification — both are documented below with full evidence.

### What changed in `tools/engine_matrix.sh`

1. **Sentinel-gated venv reuse.** Reuse now requires `"$venv/.ready"` to
   exist, not just `$venv/bin/python`. On `VENV-FAIL` or `PIP-FAIL` the venv
   directory is `rm -rf`'d before `continue`, and `.ready` is only `touch`'d
   after the install genuinely succeeds. A venv without the sentinel is
   deleted and recreated (so any half-built venv from a prior failed run is
   never silently reused).
2. **Positive-signal classification.** PASS now requires the last pytest
   line to match `[0-9]+ passed` **and** not match `(^| )(failed|error)`;
   previously it was PASS-unless-negative-match, so an empty/garbage last
   line (e.g. `ModuleNotFoundError`, `No module named pytest`) matched
   neither pattern and fell through to PASS. Each combo now starts by
   deleting any stale `$SCRATCH/$label.last`/`.log` so a previous run's
   output can never be re-read.
3. **Full output preserved.** `pytest` now redirects to `$SCRATCH/$label.log`
   (no `tee`, no no-op `if … then :; fi`); `$SCRATCH/$label.last` holds just
   the tailed summary line, which is echoed to stdout; on FAIL the script
   also prints `see $SCRATCH/$label.log`.
4. **`set -o pipefail`** added near the top.

### Two additional bugs found and fixed during the mandated end-to-end rerun

The review's required verification step ("a venv without the sentinel is
deleted and recreated; expect all 6 to be rebuilt once") is exactly what
exposed these — they were previously masked because the pre-existing
`py36-rl3559` venv from before this task was always silently reused and its
actual install command never ran for real.

**Bug A — `pip<22` collided with the implicit `--upgrade pip`.** The py3.6
combo's extras list included `pip<22` (a courtesy cap alongside
`--upgrade pip` in the same command). On a truly fresh venv (bundled pip
18.1), this produces two specifiers for the same package name in one
invocation:

```
ERROR (reproduced verbatim): Double requirement given: pip<22 (already in pip, name='pip')
```

Verified in an isolated throwaway venv that `pip install --upgrade pip
"Pillow<9" "pytest<7.1" "pypdf<4" "reportlab==3.5.59"` (no `pip<22`) lets
pip's own interpreter-compatibility resolution naturally land on pip
21.3.1 — already `< 22` — making the extra pin fully redundant. Fix: removed
`pip<22` from the py36 extras (line 12), leaving `Pillow<9 pytest<7.1
pypdf<4`. This is an auxiliary "extra pin" (per the brief's own column
header), not the reportlab pin, and was not silently changed — it's
reported here with the exact reproducing error.

**Bug B — combining `--upgrade pip` with the package installs in one
invocation, starting from py3.6's ancient bootstrap pip, silently produced a
broken Pillow install.** After fixing Bug A, the py3.6 combo installed
without error but then failed a real test:

```
FAILED test_calibration.py::test_image_left_middle_anchor - ImportError: dlopen(
  .../site-packages/PIL/_imaging.cpython-36m-darwin.so, 0x0002):
  symbol not found in flat namespace '_jpeg_resync_to_restart'
1 failed, 113 passed in 2.61s / 2.53s (reproduced on two separate fresh-venv rebuilds)
```

Diagnosis (in order of hypotheses tried and ruled out, for the record):
- *Not* an architecture/library gap: cross-checked against the real
  `/Volumes/Workspace/Development/OdooWorkbench/odoo11/venv` (Python 3.6.8,
  read-only inspection only) — its Pillow 5.4.1 imports fine there, so a
  working py3.6+Pillow combo is achievable on this machine.
- *Not* a broken/incompatible Pillow 8.4.0 wheel: `otool -L` on a **working**
  reinstall showed `_imaging...so` correctly linking
  `@loader_path/.dylibs/libjpeg.9.dylib` etc. (self-contained, delocated) —
  same wheel filename `Pillow-8.4.0-cp36-cp36m-macosx_10_10_x86_64.whl` in
  both the broken and working cases.
- *Not* pip HTTP cache corruption: cleared/bypassed suspicion by fully
  deleting and rebuilding the real `py36-rl3559` scratch venv twice more from
  a completely fresh `python3 -m venv`; the failure reproduced deterministically
  both times with the script's original single-invocation form
  (`pip install -q --upgrade pip $extras "reportlab==$pin"`), and never
  reproduced when the pip self-upgrade was issued as a separate, prior
  invocation.
- **Confirmed root cause:** combining `--upgrade pip` with other packages in
  one `pip install` command is unreliable when starting from pip 18.1 (the
  version python.org's 3.6.8 installer bundles) — pip self-upgrades itself
  mid-invocation and the same invocation's install of the remaining packages
  (Pillow in particular) can complete with exit 0 while leaving its bundled
  `.dylibs` payload incompletely extracted, producing the dlopen
  `ImportError` above only at *import* time, not at *install* time. This
  reproduced identically on two independent from-scratch venvs and never
  reproduced once the pip self-upgrade was split into its own invocation
  (verified on a third independent from-scratch venv, both via manual
  `pip install` + `from PIL import Image` and via a full
  `engine/native/tests` pytest run: 114 passed).

Fix: split the install into two invocations — `pip install -q --upgrade pip`
first, then `pip install -q $extras "reportlab==$pin"` — applied uniformly to
all six combos (harmless no-op timing difference for py3.9/3.10/3.12, whose
bundled pip is already modern). No reportlab pin was changed; no file under
`engine/native/` was touched.

### Commands run / verification

- `bash -n tools/engine_matrix.sh` → syntax OK.
- Full end-to-end reruns: the review's mandated procedure ("a venv without
  the sentinel is deleted and recreated") meant none of the six venvs (none
  had a `.ready` sentinel from before this fix) were reused — **all 6 were
  rebuilt from scratch**, as anticipated by the review. Iterated through the
  above two bugs across several rebuild attempts; final two consecutive
  clean runs (script unmodified between them, `py36-rl3559` deleted and
  rebuilt from scratch before each) both produced:

```
== creating py36-rl3559 (/Library/Frameworks/Python.framework/Versions/3.6/bin/python3, reportlab==3.5.59)
== py36-rl3559: python 3.6.8 reportlab 3.5.59
114 passed in 5.26s
== py39-rl3559: python 3.9.24 reportlab 3.5.59
114 passed in 0.59s
== py39-rl4410: python 3.9.24 reportlab 4.4.10
114 passed in 0.70s
== py39-rl500: python 3.9.24 reportlab 5.0.0
114 passed in 0.71s
== py310-rl368: python 3.10.19 reportlab 3.6.8
114 passed, 1 warning in 0.59s
== py312-rl410: python 3.12.12 reportlab 4.1.0
114 passed, 1 warning in 0.65s

engine matrix:
  py36-rl3559|PASS|114 passed in 5.26s
  py39-rl3559|PASS|114 passed in 0.59s
  py39-rl4410|PASS|114 passed in 0.70s
  py39-rl500|PASS|114 passed in 0.71s
  py310-rl368|PASS|114 passed, 1 warning in 0.59s
  py312-rl410|PASS|114 passed, 1 warning in 0.65s
```

Exit code: `0` both times.

### Negative test for finding 1 (venv-reuse-after-failed-install)

Per the review's instructions: copied the script to a scratchpad-only file
(`/private/tmp/.../scratchpad/engine_matrix_negtest.sh`, never added to the
repo, deleted afterward — `git status --short` confirms it was never
tracked), trimmed `COMBOS` to a single entry, and changed that entry's
reportlab pin to the nonexistent `0.0.0`. Ran it twice with
`SCRATCH_VENVS=/private/tmp/.../scratchpad/venvs-negtest` (a dedicated,
disposable scratch dir, never touching the real `venvs/` dir):

Run 1 (fresh):
```
== creating py36-rl3559 (/Library/Frameworks/Python.framework/Versions/3.6/bin/python3, reportlab==0.0.0)
ERROR: Could not find a version that satisfies the requirement reportlab==0.0.0 (from versions: 2.3, ..., 3.6.8)
ERROR: No matching distribution found for reportlab==0.0.0

engine matrix:
  py36-rl3559|PIP-FAIL
RUN1 EXIT:1
```

State check between runs: `ls` on the negtest scratch dir showed the venv
directory itself was gone (only cleaned up by the `rm -rf "$venv"` on
`PIP-FAIL`), so nothing half-built was left behind.

Run 2 (immediate rerun, same broken pin):
```
== creating py36-rl3559 (/Library/Frameworks/Python.framework/Versions/3.6/bin/python3, reportlab==0.0.0)
ERROR: Could not find a version that satisfies the requirement reportlab==0.0.0 (from versions: 2.3, ..., 3.6.8)
ERROR: No matching distribution found for reportlab==0.0.0

engine matrix:
  py36-rl3559|PIP-FAIL
RUN2 EXIT:1
```

Both runs correctly report `PIP-FAIL` with exit 1 — never a false PASS. This
confirms the old bug (mere presence of `$venv/bin/python` triggering silent
reuse of a half-built venv on the second run) is fixed: the venv is
`rm -rf`'d on failure and the `.ready` sentinel is only ever written after a
genuinely successful install.

Cleanup performed: `rm -rf` on the negtest `venvs-negtest` scratch dir and
the negtest script copy. `git status --short` in the repo shows no trace of
either (they never existed inside the repo tree).

### Files changed (fix round)

- Modified: `tools/engine_matrix.sh` (27 insertions, 7 deletions)
- No other files touched; nothing under `engine/native/` was modified.

Commit: `77efb21` — "tools: fix engine_matrix.sh false-PASS and pip
self-upgrade bugs" (`git status --short` after commit is clean).

### Self-review (fix round)

- `bash -n` passes.
- Rerun end-to-end from a clean `.ready`-less state (all 6 rebuilt, as the
  review anticipated) — exit 0, 6/6 PASS, reproduced twice.
- Negative test demonstrates finding 1 is fixed: two consecutive runs against
  a deliberately-broken pin both report `PIP-FAIL`/exit 1, never PASS.
- The two extra bugs found (`pip<22` double-requirement; pip self-upgrade
  corrupting a same-invocation Pillow install) were diagnosed with concrete,
  reproducible evidence before being fixed — not guessed at. Neither
  required touching `engine/native/` or changing a reportlab pin; both
  fixes are minimal and scoped to the install-command construction.
- No unrelated files reformatted; both commits are clean, scoped diffs.

### Concerns

None remaining. All six combinations pass deterministically (verified across
three full end-to-end rebuilds of the py3.6 combo specifically, since it was
the one that surfaced real bugs) with 114 tests each.
