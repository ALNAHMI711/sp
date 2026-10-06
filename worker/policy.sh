#!/usr/bin/env bash
set -euo pipefail

TARGET_REPO="${TARGET_REPO:?TARGET_REPO is required}"
TASK="${TASK:-Inspect repository and report blockers}"

case "$TARGET_REPO" in
  ALNAHMI711/Ahmed-Alnahmi-711|ALNAHMI711/autonomous-business-manager|ALNAHMI711/-|ALNAHMI711/tte|ALNAHMI711/sp) ;;
  *) echo "POLICY_DENY: repository not approved"; exit 10 ;;
esac

blocked='(LIVE|live trading|withdrawal|withdrawals|secret rotation|rotate secret|production deploy|production deployment|delete repository|drop database|force push|liquidat(e|ion))'
if printf '%s\n' "$TASK" | grep -Eiq "$blocked"; then
  echo "POLICY_DENY: sensitive task requires explicit approval"
  exit 11
fi

echo "POLICY_ALLOW: safe inspection/testing task"
