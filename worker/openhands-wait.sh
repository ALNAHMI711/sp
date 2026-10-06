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
terminal = {"finished", "error", "stuck"}
started = time.time()

def get(path):
    req = urllib.request.Request(
        base + path,
        headers={"X-Session-API-Key": api_key},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

while time.time() - started < max_wait:
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
