#!/usr/bin/env bash
# Run the engine's pytest suite under every (Python, reportlab) pair the nine Odoo venvs ship.
# Scratch venvs are created on first use and reused afterwards.
set -u
set -o pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH_VENVS:-/private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/venvs}"
mkdir -p "$SCRATCH"

# label | interpreter | reportlab pin | extra pins
COMBOS=(
  "py36-rl3559|/Library/Frameworks/Python.framework/Versions/3.6/bin/python3|3.5.59|Pillow<9 pytest<7.1 pypdf<4"
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
  rm -f "$SCRATCH/$label.last" "$SCRATCH/$label.log"
  if [ ! -f "$venv/.ready" ]; then
    rm -rf "$venv"
    echo "== creating $label ($py, reportlab==$pin)"
    "$py" -m venv "$venv" || { rm -rf "$venv"; results+=("$label|VENV-FAIL"); fail=1; continue; }
    # Upgrade pip in its own invocation, separate from the package installs below.
    # Combining "--upgrade pip" with other packages in one command is unreliable when
    # starting from an ancient bootstrap pip (observed: py3.6's bundled pip 18.1 would
    # self-upgrade mid-resolution and leave Pillow's bundled .dylibs incompletely
    # extracted, producing a dlopen ImportError at test time despite `pip install`
    # itself reporting success).
    "$venv/bin/python" -m pip install -q --upgrade pip \
      || { rm -rf "$venv"; results+=("$label|PIP-FAIL"); fail=1; continue; }
    # shellcheck disable=SC2086
    "$venv/bin/python" -m pip install -q $extras "reportlab==$pin" \
      || { rm -rf "$venv"; results+=("$label|PIP-FAIL"); fail=1; continue; }
    touch "$venv/.ready"
  fi
  rl="$("$venv/bin/python" -c 'import reportlab; print(reportlab.Version)' 2>/dev/null)"
  echo "== $label: python $("$venv/bin/python" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') reportlab $rl"
  (cd "$REPO/engine/native/tests" && "$venv/bin/python" -m pytest -q -p no:cacheprovider) > "$SCRATCH/$label.log" 2>&1
  tail -1 "$SCRATCH/$label.log" > "$SCRATCH/$label.last"
  last="$(cat "$SCRATCH/$label.last")"
  echo "$last"
  if echo "$last" | grep -qE "[0-9]+ passed" && ! echo "$last" | grep -qE "(^| )(failed|error)"; then
    results+=("$label|PASS|$last")
  else
    echo "   see $SCRATCH/$label.log"
    results+=("$label|FAIL|$last")
    fail=1
  fi
done

echo; echo "engine matrix:"
for r in "${results[@]}"; do echo "  $r"; done
exit $fail
