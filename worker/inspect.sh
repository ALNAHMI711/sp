#!/usr/bin/env bash
set -euo pipefail

TARGET_REPO="${TARGET_REPO:?TARGET_REPO is required}"
TASK="${TASK:-Inspect repository, run safe checks, and report blockers}"
WORKDIR="${RUNNER_TEMP:-/tmp}/autonomous-target"

case "$TARGET_REPO" in
  ALNAHMI711/Ahmed-Alnahmi-711|ALNAHMI711/autonomous-business-manager|ALNAHMI711/-|ALNAHMI711/tte) ;;
  *) echo "Blocked: target repository is not in the approved initial set."; exit 2 ;;
esac

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"

echo "== Autonomous Worker =="
echo "Repository: $TARGET_REPO"
echo "Task: $TASK"

if ! git clone --depth 1 "https://github.com/$TARGET_REPO.git" "$WORKDIR/repo"; then
  echo "Blocked: repository clone failed. A scoped GitHub credential may be required for private repositories."
  exit 3
fi

cd "$WORKDIR/repo"
{
  echo "# Autonomous inspection report"
  echo
  echo "- Repository: $TARGET_REPO"
  echo "- Commit: $(git rev-parse HEAD)"
  echo "- Task: $TASK"
  echo
  echo "## Repository shape"
  printf '%s\\n' "```"
  find . -maxdepth 2 -type f ! -path './.git/*' | sort | head -200
  printf '%s\\n' "```"
  echo
  echo "## Detected project files"
  for f in pyproject.toml requirements.txt package.json Dockerfile docker-compose.yml compose.yml; do
    [ -f "$f" ] && echo "- $f"
  done
} > "$GITHUB_WORKSPACE/inspection-report.md"

echo "Inspection complete: $GITHUB_WORKSPACE/inspection-report.md"
