#!/usr/bin/env bash
set -euo pipefail

TARGET_REPO="${TARGET_REPO:?TARGET_REPO is required}"
TASK="${TASK:-Inspect repository and report blockers}"

if [ -n "${CONTROL_ALLOWED_REPOS:-}" ]; then
  case ",${CONTROL_ALLOWED_REPOS}," in
    *,${TARGET_REPO},*) ;;
    *) echo "Blocked: target repository is not in the configured allowlist."; exit 2 ;;
  esac
else
  if ! grep -Fxq "$TARGET_REPO" "$(dirname "$0")/approved_repositories.txt"; then
    echo "POLICY_DENY: repository not approved"
    exit 2
  fi
fi

blocked='(LIVE|live trading|withdrawal|withdrawals|secret rotation|rotate secret|production deploy|production deployment|delete repository|drop database|force push|liquidat(e|ion))'
if printf '%s\n' "$TASK" | grep -Eiq "$blocked"; then
  echo "POLICY_DENY: sensitive task requires explicit approval"
  exit 11
fi

echo "POLICY_ALLOW: safe inspection/testing task"
