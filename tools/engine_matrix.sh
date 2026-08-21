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
