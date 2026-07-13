#!/usr/bin/env bash
set -uo pipefail

BATCH="${BATCH_A_ROOT:-/data/adarare_exp/batch_a}"
MARKER="${BATCH}/manifests/latest_formal_root.txt"
[[ -f "$MARKER" ]] || { echo "missing formal root marker: $MARKER" >&2; exit 1; }
FORMAL_ROOT="$(<"$MARKER")"
LOG="${FORMAL_ROOT}/logs/monitor.log"
INTERVAL="${BATCH_A_MONITOR_INTERVAL_SECONDS:-300}"
mkdir -p "$(dirname "$LOG")"

while true; do
  {
    echo "===== $(date -Is) ====="
    echo "formal_root=$FORMAL_ROOT"
    df -h / /data
    docker system df || true
    echo "docker_containers=$(docker ps -q | wc -l)"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | head -100 || true
    python3 - "$FORMAL_ROOT" <<'PY'
from pathlib import Path
import sqlite3,sys
root=Path(sys.argv[1])
db=root/'experiment-data'/'local.db'
if not db.is_file():
    print('database=NOT_CREATED')
    raise SystemExit
c=sqlite3.connect(db)
trials=c.execute('select count(*) from trial').fetchone()[0]
started=c.execute('select count(*) from trial where time_started is not null').fetchone()[0]
ended=c.execute('select count(*) from trial where time_ended is not null').fetchone()[0]
snapshots=c.execute('select count(*) from snapshot').fetchone()[0]
cells=c.execute('select count(*) from (select benchmark,fuzzer from trial group by benchmark,fuzzer)').fetchone()[0]
print(f'trials={trials} cells={cells} started={started} ended={ended} snapshots={snapshots}')
for row in c.execute('select benchmark,fuzzer,count(*),sum(time_started is not null),sum(time_ended is not null) from trial group by benchmark,fuzzer order by benchmark,fuzzer'):
    print('cell='+'\t'.join(map(str,row)))
PY
    tmux list-sessions 2>/dev/null || true
    echo
  } >> "$LOG" 2>&1

  if ! tmux has-session -t adarare-batcha-formal 2>/dev/null; then
    echo "formal tmux ended at $(date -Is); monitor stopping without deleting or restarting anything" >> "$LOG"
    break
  fi
  sleep "$INTERVAL"
done
