#!/usr/bin/env bash
set -euo pipefail

: "${OPENHANDS_AGENT_SERVER_URL:?OPENHANDS_AGENT_SERVER_URL is required}"
: "${OPENHANDS_SESSION_API_KEY:?OPENHANDS_SESSION_API_KEY is required}"

BASE="${OPENHANDS_AGENT_SERVER_URL%/}"
AUTH_HEADER="X-Session-API-Key: $OPENHANDS_SESSION_API_KEY"

echo "== OpenHands bridge health check =="
health="$(curl -fsS --max-time 15 "$BASE/health")"
ready="$(curl -fsS --max-time 15 "$BASE/ready")"
info="$(curl -fsS --max-time 15 -H "$AUTH_HEADER" "$BASE/server_info")"

printf '%s\n' "$health"
printf '%s\n' "$ready"
printf '%s\n' "$info"

echo "OPENHANDS_BRIDGE_STATUS=READY"
