#!/usr/bin/env bash
set -euo pipefail

: "${OPENHANDS_AGENT_SERVER_URL:?OPENHANDS_AGENT_SERVER_URL is required}"
: "${OPENHANDS_SESSION_API_KEY:?OPENHANDS_SESSION_API_KEY is required}"
: "${OPENHANDS_WORKING_DIR:?OPENHANDS_WORKING_DIR is required}"
: "${OPENHANDS_TASK:?OPENHANDS_TASK is required}"

BASE="${OPENHANDS_AGENT_SERVER_URL%/}"
AUTH_HEADER="X-Session-API-Key: $OPENHANDS_SESSION_API_KEY"

python - "$BASE" "$OPENHANDS_WORKING_DIR" "$OPENHANDS_TASK" "$AUTH_HEADER" <<'PY'
import json, sys, urllib.request, urllib.error

base, working_dir, task, auth = sys.argv[1:]
payload = {
    "initial_message": {
        "role": "user",
        "content": [{"type": "text", "text": task}],
        "run": True,
    },
    "workspace": {"working_dir": working_dir},
}
req = urllib.request.Request(
    base + "/api/conversations",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "X-Session-API-Key": auth.split(": ", 1)[1]},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=120) as response:
        data = json.load(response)
except urllib.error.HTTPError as exc:
    print(f"OPENHANDS_START_FAILED status={exc.code}", file=sys.stderr)
    print(exc.read().decode(errors="replace"), file=sys.stderr)
    raise SystemExit(2)

conversation_id = data.get("id")
if not conversation_id:
    print("OPENHANDS_START_FAILED missing conversation id", file=sys.stderr)
    raise SystemExit(3)

print(json.dumps({"conversation_id": conversation_id, "status": data.get("execution_status", "unknown")}))
PY
