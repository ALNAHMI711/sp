#!/usr/bin/env bash
set -euo pipefail

: "${OPENHANDS_AGENT_SERVER_URL:?OPENHANDS_AGENT_SERVER_URL is required}"
: "${OPENHANDS_SESSION_API_KEY:?OPENHANDS_SESSION_API_KEY is required}"
: "${OPENHANDS_CONVERSATION_ID:?OPENHANDS_CONVERSATION_ID is required}"

BASE="${OPENHANDS_AGENT_SERVER_URL%/}"
AUTH_HEADER="X-Session-API-Key: $OPENHANDS_SESSION_API_KEY"
MAX_WAIT="${OPENHANDS_MAX_WAIT_SECONDS:-3600}"
INTERVAL="${OPENHANDS_POLL_INTERVAL_SECONDS:-5}"

python - "$BASE" "$OPENHANDS_CONVERSATION_ID" "$OPENHANDS_SESSION_API_KEY" "$MAX_WAIT" "$INTERVAL" <<'PY'
import json, sys, time, urllib.request, urllib.error

base, conversation_id, api_key, max_wait, interval = sys.argv[1:]
max_wait, interval = int(max_wait), int(interval)
terminal = {"finished", "error", "stuck", "stopped"}
started = time.time()

def post(path):
    req = urllib.request.Request(
        base + path,
        data=b"",
        headers={"X-Session-API-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response) if response.readable() else {}

def get(path):
    req = urllib.request.Request(
        base + path,
        headers={"X-Session-API-Key": api_key},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

queue_db = __import__("os").environ.get("CONTROL_QUEUE_DB", "")
job_id = __import__("os").environ.get("CONTROL_JOB_ID", "")
kill_file = __import__("os").environ.get("CONTROL_KILL_SWITCH_FILE", "")
while time.time() - started < max_wait:
    if job_id and queue_db:
        import sqlite3
        with sqlite3.connect(queue_db, timeout=3) as db:
            row = db.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        requested = row and row[0] == "cancel_requested"
    else:
        requested = False
    if requested or (kill_file and __import__("os").path.exists(kill_file)):
        try:
            post(f"/api/conversations/{conversation_id}/interrupt")
            print("OPENHANDS_STOP_REQUESTED=1", flush=True)
        except Exception as exc:
            print(f"OPENHANDS_STOP_FAILED={type(exc).__name__}", file=sys.stderr)
            raise SystemExit(22)
        raise SystemExit(23)

    data = get(f"/api/conversations/{conversation_id}")
    status = data.get("execution_status", "unknown")
    print(f"OPENHANDS_STATUS={status}", flush=True)
    if status in terminal:
        final = get(f"/api/conversations/{conversation_id}/agent_final_response")
        response = final.get("response", "") if isinstance(final, dict) else ""
        print(json.dumps({"conversation_id": conversation_id, "status": status, "final_response": response}))
        raise SystemExit(0 if status == "finished" else 20)
    time.sleep(interval)

print("OPENHANDS_STATUS=TIMEOUT", file=sys.stderr)
raise SystemExit(21)
PY
