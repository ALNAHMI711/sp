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
echo "- Commit: $(git rev-parse HEAD)" >> "$REPORT"
echo >> "$REPORT"

check() {
  local name="$1"
  local result="$2"
  checks=$((checks+1))
  echo "- $name: $result" >> "$REPORT"
  if [ "$result" != "PASS" ]; then critical=$((critical+1)); fi
}

if [ -d .github/workflows ]; then
  check "Workflow configuration present" "PASS"
else
  check "Workflow configuration present" "WARN"
fi

if [ -d tests ] || [ -f pytest.ini ] || [ -f pyproject.toml ] || [ -f package.json ]; then
  check "Project test surface detected" "PASS"
else
  check "Project test surface detected" "WARN"
fi

if git status --porcelain | grep -q .; then
  check "Working tree clean" "FAIL"
else
  check "Working tree clean" "PASS"
fi

if grep -RniE "(TODO|FIXME|XXX)" --exclude-dir=.git . >/dev/null 2>&1; then
  echo "- Outstanding TODO/FIXME markers: WARN" >> "$REPORT"
else
  echo "- Outstanding TODO/FIXME markers: PASS" >> "$REPORT"
fi

echo >> "$REPORT"
if [ "$critical" -eq 0 ]; then
  echo "COMPLETION_STATUS=READY_FOR_VERIFICATION" | tee -a "$REPORT"
else
  echo "COMPLETION_STATUS=BLOCKED" | tee -a "$REPORT"
  exit 30
fi