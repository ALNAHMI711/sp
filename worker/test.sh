#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:?repository directory required}"
cd "$REPO_DIR"
REPORT="${GITHUB_WORKSPACE:-.}/test-report.md"
: > "$REPORT"
echo "# Autonomous test report" >> "$REPORT"
echo >> "$REPORT"

failures=0
ran_python_tests=0

run_pytest() {
  local label="$1"
  shift
  ran_python_tests=1
  {
    echo
    echo "## $label"
    echo
  } >> "$REPORT"
  if python -m pytest -q "$@" >> "$REPORT" 2>&1; then
    echo "- $label: PASS" >> "$REPORT"
  else
    echo "- $label: FAIL" >> "$REPORT"
    failures=$((failures+1))
  fi
}

if command -v python >/dev/null 2>&1; then
  # This repository has two Python test roots with different import paths.
  # Run each from its own project root instead of collecting both from the
  # repository root (which breaks unified-dev-hub's app.main imports).
  if [ -d tests ]; then
    run_pytest "Repository tests" tests
  fi

  if [ -d unified-dev-hub/tests ]; then
    (
      cd unified-dev-hub
      run_pytest "Unified Dev Hub tests" tests
    )
  elif [ "$ran_python_tests" -eq 0 ] && { [ -f pyproject.toml ] || [ -f pytest.ini ]; }; then
    run_pytest "Python tests" .
  fi
fi

if [ -f package.json ] && command -v npm >/dev/null 2>&1; then
  if npm test --if-present >> "$REPORT" 2>&1; then
    echo "- npm tests: PASS" >> "$REPORT"
  else
    echo "- npm tests: FAIL" >> "$REPORT"
    failures=$((failures+1))
  fi
fi

if [ "$failures" -gt 0 ]; then echo "TEST_STATUS=FAIL"; exit 20; fi
echo "TEST_STATUS=PASS"
