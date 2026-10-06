#!/usr/bin/env bash
set -euo pipefail

: "${OPENHANDS_AGENT_SERVER_URL:?OPENHANDS_AGENT_SERVER_URL is required}"
: "${OPENHANDS_SESSION_API_KEY:?OPENHANDS_SESSION_API_KEY is required}"
: "${OPENHANDS_CONVERSATION_ID:?OPENHANDS_CONVERSATION_ID is required}"

BASE="${OPENHANDS_AGENT_SERVER_URL%/}"

python - "$BASE" "$OPENHANDS_CONVERSATION_ID" "$OPENHANDS_SESSION_API_KEY" <<'PY'
import json, sys, urllib.request, urllib.error

base, conversation_id, api_key = sys.argv[1:]
req = urllib.request.Request(
    f"{base}/api/conversations/{conversation_id}/interrupt",
    data=b"",
    headers={"X-Session-API-Key": api_key},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as response:
        print(response.read().decode(errors="replace"))
except urllib.error.HTTPError as exc:
    print(f"OPENHANDS_STOP_FAILED status={exc.code}", file=sys.stderr)
    print(exc.read().decode(errors="replace"), file=sys.stderr)
    raise SystemExit(2)

print("OPENHANDS_STOP_REQUESTED=1")
