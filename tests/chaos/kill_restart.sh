#!/usr/bin/env bash
# Chaos check S3: kill -9 the server while a run waits for a human, restart, decide from the Console.
# Pass = identical message, checkpoint and wait counts before the kill and after the restart, a resume event,
# no duplicate idempotency key, and the run completes once the humans answer.
# Offline (recorded model answers), no Slack. Usage: bash tests/chaos/kill_restart.sh [port]
set -u
cd "$(dirname "$0")/../.." || exit 1
PORT="${1:-8771}"; URL="http://127.0.0.1:$PORT"; STATE="var/chaos-kill"; PY=.venv/bin/python
rm -rf "$STATE"; mkdir -p "$STATE"

start() {
  COLEX_VAR="$STATE" COLEX_PORT="$PORT" COLEX_SLACK=0 COLEX_OFFLINE=1 nohup "$PY" -m colex.server \
    > "$STATE/server.log" 2>&1 &
  echo $! > "$STATE/pid"
  for _ in $(seq 1 40); do curl -s -o /dev/null -m 2 "$URL/api/runs" && return 0; sleep 0.5; done
  echo "server did not start"; cat "$STATE/server.log"; exit 1
}
count() { COLEX_VAR="$STATE" "$PY" - <<'EOF'
from colex import db
c = db.connect()
print(c.execute("select count(*) from outbox").fetchone()[0], c.execute("select count(*) from checkpoints").fetchone()[0],
      c.execute("select count(*) from waits where status='pending'").fetchone()[0],
      ",".join(r[0] for r in c.execute("select status from runs")))
EOF
}
wait_for() {  # wait until the run status starts with $1 and stays the same for two checks
  last=""
  for _ in $(seq 1 80); do
    now="$(count)"
    case "$(echo "$now" | cut -d' ' -f4)" in "$1"*) [ "$now" = "$last" ] && return 0;; esac
    last="$now"; sleep 0.5
  done
  echo "timeout waiting for status $1*, got: $(count)"; return 1
}
answer_all() {  # decide every pending wait: first option for a question, approve for a review (as the demo does)
  COLEX_VAR="$STATE" "$PY" - > "$STATE/waits.txt" <<'EOF'
from urllib.parse import quote
from colex.runtime import store
for w in store.waits(status="pending"):
    decision = "approve" if w["kind"] == "review" else w["payload"]["question"]["options"][0]
    print(quote(w["wait_id"], safe=""), quote(decision, safe=""))
EOF
  while read -r wait decision; do
    curl -s -o /dev/null -m 20 -X POST -d "decision=$decision" "$URL/act/$wait"
  done < "$STATE/waits.txt"
}

start
curl -s -o /dev/null -m 10 -X POST -d "celex=32024R0886" "$URL/feed/publish"
wait_for waiting_ || { kill -9 "$(cat "$STATE/pid")"; exit 1; }
BEFORE="$(count)"; echo "before kill:   messages checkpoints pending-waits status = $BEFORE"

kill -9 "$(cat "$STATE/pid")"; sleep 1
kill -0 "$(cat "$STATE/pid")" 2>/dev/null && { echo "server survived kill -9"; exit 1; }
start; sleep 4
AFTER="$(count)"; echo "after restart: messages checkpoints pending-waits status = $AFTER"

for _ in 1 2 3 4 5; do   # answering can open further waits; repeat until the run is done
  answer_all; sleep 3
  [ "$(count | cut -d' ' -f4)" = "done" ] && break
done
FINAL="$(count)"; echo "after answers: messages checkpoints pending-waits status = $FINAL"
DUPES=$(COLEX_VAR="$STATE" "$PY" -c "from colex import db; print(db.connect().execute('select count(*) - count(distinct idem_key) from outbox').fetchone()[0])")
RESUMED=$(COLEX_VAR="$STATE" "$PY" -c "from colex import db; print(db.connect().execute(\"select count(*) from audit_events where summary like 'Resumed after restart%'\").fetchone()[0])")
kill "$(cat "$STATE/pid")" 2>/dev/null

[ "$BEFORE" = "$AFTER" ] && [ "$(echo "$FINAL" | cut -d' ' -f4)" = "done" ] && [ "$RESUMED" -ge 1 ] \
  && [ "$DUPES" = "0" ] \
  && { echo "PASS: no duplicate message after kill -9 and restart; resume event recorded; run completed"; exit 0; }
echo "FAIL"; exit 1
