#!/usr/bin/env bash
# Install vNN/pentaho_reports into a fresh throwaway DB on the local Odoo NN and run its tests.
# Usage: tools/odoo_install_test.sh 17      -> prints "RESULT v17 PASS" or "RESULT v17 FAIL", exit 0/1.
# Always drops the DB. Log kept at $LOGDIR/odoo_vNN.log.
set -u
N="${1:?odoo major version, e.g. 17}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WB=/Volumes/Workspace/Development/OdooWorkbench/odoo$N
PY="$WB/venv/bin/python"
ODOO_BIN="$WB/odoo/odoo-bin"
DB="pentaho_test_v$N"
PORT="180$N"
LOGDIR="${LOGDIR:-/private/tmp/claude-501/-Volumes-Workspace-Development-Workbench/5a2b955a-0385-4d47-af11-aedcf53c2e14/scratchpad/odoo-logs}"
mkdir -p "$LOGDIR"; LOG="$LOGDIR/odoo_v$N.log"
# Odoo opens --logfile in append mode; truncate so a stale FAIL/Traceback from
# a previous run of this script can't make the grep below false-positive.
: > "$LOG"

[ -x "$PY" ] || { echo "RESULT v$N FAIL (no venv python at $PY)"; exit 1; }
[ -f "$ODOO_BIN" ] || { echo "RESULT v$N FAIL (no odoo-bin at $ODOO_BIN)"; exit 1; }
[ -d "$REPO/v$N/pentaho_reports" ] || { echo "RESULT v$N FAIL (no v$N/pentaho_reports)"; exit 1; }

cleanup() { dropdb --if-exists "$DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
createdb -O "odoo$N" "$DB" || { echo "RESULT v$N FAIL (createdb)"; exit 1; }

TEST_TAGS=()
if [ "$N" -ge 12 ]; then TEST_TAGS=(--test-tags "/pentaho_reports"); fi
# Odoo 11-15 know --longpolling-port, 16+ --gevent-port (unknown options abort the run).
if [ "$N" -ge 16 ]; then LP_FLAG=(--gevent-port=$((PORT+1000))); else LP_FLAG=(--longpolling-port=$((PORT+1000))); fi

( cd "$WB/odoo" && "$PY" "$ODOO_BIN" \
    -d "$DB" -r "odoo$N" --db_host=localhost \
    --addons-path="$WB/odoo/addons,$REPO/v$N" \
    -i pentaho_reports --test-enable "${TEST_TAGS[@]}" \
    --stop-after-init --without-demo=all \
    --http-port="$PORT" "${LP_FLAG[@]}" \
    --log-level=test --logfile="$LOG" ) 2>>"$LOG"
rc=$?

ran=$(grep -cE "pentaho_reports.*(test_[a-z_]+|Starting|Ran [0-9]+ tests?)" "$LOG" || true)
bad=$(grep -E "(ERROR|CRITICAL) .*(pentaho_reports|odoo\.tests|odoo\.modules\.loading|odoo\.sql_db|Traceback)|FAIL: |ERROR: test_|^Traceback" "$LOG" | grep -v "test-tags" | head -20 || true)
echo "--- v$N: exit=$rc, test lines=$ran"
if [ $rc -ne 0 ] || [ -n "$bad" ] || [ "$ran" -eq 0 ]; then
  echo "$bad"; echo "RESULT v$N FAIL (see $LOG)"; exit 1
fi
echo "RESULT v$N PASS"
