#!/usr/bin/env bash
set -euo pipefail

: "${OPENHANDS_AGENT_SERVER_URL:?OPENHANDS_AGENT_SERVER_URL is required}"
: "${OPENHANDS_SESSION_API_KEY:?OPENHANDS_SESSION_API_KEY is required}"
: "${OPENHANDS_WORKING_DIR:?OPENHANDS_WORKING_DIR is required}"
: "${OPENHANDS_TASK:?OPENHANDS_TASK is required}"

case "${OPENHANDS_TASK}" in
  *LIVE*|*live*|*withdrawal*|*Withdraw*|*secret rotation*|*rotate secret*|*production deploy*|*delete repository*|*drop database*|*force push*|*liquidate*)
    echo "BLOCKED: sensitive task requires explicit approval." >&2
    exit 10
    ;;
esac

START_OUTPUT="$(bash "$(dirname "$0")/openhands-start.sh")"
printf '%s
' "$START_OUTPUT"

CONVERSATION_ID="$(python -c 'import json,sys; print(json.load(sys.stdin)["conversation_id"])' <<<"$START_OUTPUT")"
export OPENHANDS_CONVERSATION_ID="$CONVERSATION_ID"

bash "$(dirname "$0")/openhands-wait.sh"
