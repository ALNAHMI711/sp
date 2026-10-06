#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:?repository directory required}"
cd "$REPO_DIR"
REPORT="${GITHUB_WORKSPACE:-.}/completion-report.md"

critical=0
checks=0
: > "$REPORT"
echo "# Autonomous completion report" >> "$REPORT"
echo >> "$REPORT"
echo "- Repository: ${TARGET_REPO:-unknown}" >> "$REPORT"
echo "- Commit before agent work: $(git rev-parse HEAD)" >> "$REPORT"
echo "- Write mode: ${WRITE_MODE:-read_only}" >> "$REPORT"
echo >> "$REPORT"

check() {
  local name="$1" result="$2"
  checks=$((checks+1))
  echo "- $name: $result" >> "$REPORT"
  [ "$result" = "PASS" ] || critical=$((critical+1))
}

[ -d .github/workflows ] && check "Workflow configuration present" "PASS" || check "Workflow configuration present" "FAIL"

if [ -d tests ] || [ -f pytest.ini ] || [ -f pyproject.toml ] || [ -f package.json ]; then
  check "Project test surface detected" "PASS"
else
  check "Project test surface detected" "FAIL"
fi

if [ "${WRITE_MODE:-read_only}" = "propose_changes" ]; then
  if git status --porcelain | grep -q .; then
    check "Proposed changes detected" "PASS"
    git diff --stat >> "$REPORT" || true
  else
    check "Proposed changes detected" "FAIL"
  fi
else
  if git status --porcelain | grep -q .; then
    check "Read-only working tree" "FAIL"
  else
    check "Read-only working tree" "PASS"
  fi
fi

if [ -n "${OPENHANDS_STATUS:-}" ]; then
  case "$OPENHANDS_STATUS" in
    finished) check "OpenHands execution" "PASS" ;;
    *) check "OpenHands execution" "FAIL" ;;
  esac
else
  echo "- OpenHands execution: NOT_RUN (CI-only verification)" >> "$REPORT"
fi

if grep -RniE "(TODO|FIXME|XXX)" --exclude-dir=.git . >/dev/null 2>&1; then
  echo "- Outstanding TODO/FIXME markers: WARN" >> "$REPORT"
else
  echo "- Outstanding TODO/FIXME markers: PASS" >> "$REPORT"
fi

echo >> "$REPORT"
if [ "$critical" -eq 0 ]; then
  echo "COMPLETION_STATUS=READY_FOR_REVIEW" | tee -a "$REPORT"
else
  echo "COMPLETION_STATUS=BLOCKED" | tee -a "$REPORT"
  exit 30
fi