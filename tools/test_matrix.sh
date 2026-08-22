#!/usr/bin/env bash
# The acceptance run for "pentaho_reports works on Odoo 11-19".
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
WB=/Volumes/Workspace/Development/OdooWorkbench
PY36=/Library/Frameworks/Python.framework/Versions/3.6/bin/python3
rows=(); fail=0
mark() { rows+=("$1|$2"); [ "$2" = PASS ] || fail=1; }

echo "### 1. drift"
python3 tools/check_drift.py && mark drift PASS || mark drift FAIL

echo "### 2. compileall per folder (each Odoo's own interpreter) + engine on py3.6"
"$PY36" -m compileall -q engine/native && mark "compile engine@py3.6" PASS || mark "compile engine@py3.6" FAIL
for N in 11 12 13 14 15 16 17 18 19; do
  PY="$WB/odoo$N/venv/bin/python"
  if [ -x "$PY" ] && "$PY" -m compileall -q "v$N/pentaho_reports"; then mark "compile v$N" PASS; else mark "compile v$N" FAIL; fi
done
find . -name __pycache__ -type d -prune -exec rm -rf {} +

echo "### 3. engine matrix (Python × reportlab)"
tools/engine_matrix.sh && mark "engine matrix" PASS || mark "engine matrix" FAIL

echo "### 4. install + module tests on each Odoo (throwaway DBs)"
for N in 11 12 13 14 15 16 17 18 19; do
  if tools/odoo_install_test.sh "$N"; then mark "odoo v$N install+tests" PASS; else mark "odoo v$N install+tests" FAIL; fi
done

echo; echo "==================== pentaho_reports test matrix ===================="
for r in "${rows[@]}"; do IFS='|' read -r k v <<<"$r"; printf "  %-32s %s\n" "$k" "$v"; done
echo "====================================================================="
exit $fail
