#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:?repository directory required}"
cd "$REPO_DIR"
REPORT="${GITHUB_WORKSPACE:-.}/test-report.md"
: > "$REPORT"
echo "# Autonomous test report" >> "$REPORT"
echo >> "$REPORT"

failures=0

if [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -d tests ]; then
  if command -v python >/dev/null 2>&1; then
    if python -m pytest -q >> "$REPORT" 2>&1; then echo "- Python tests: PASS" >> "$REPORT"; else echo "- Python tests: FAIL" >> "$REPORT"; failures=$((failures+1)); fi
  fi
fi

if [ -f package.json ] && command -v npm >/dev/null 2>&1; then
  if npm test --if-present >> "$REPORT" 2>&1; then echo "- npm tests: PASS" >> "$REPORT"; else echo "- npm tests: FAIL" >> "$REPORT"; failures=$((failures+1)); fi
fi

if [ "$failures" -gt 0 ]; then echo "TEST_STATUS=FAIL"; exit 20; fi
echo "TEST_STATUS=PASS"
