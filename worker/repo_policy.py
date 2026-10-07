"""Single source of truth for repositories approved for autonomous execution."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_APPROVED_REPOSITORIES = frozenset({
    "ALNAHMI711/Ahmed-Alnahmi-711",
    "ALNAHMI711/autonomous-business-manager",
    "ALNAHMI711/-",
    "ALNAHMI711/tte",
    "ALNAHMI711/sp",
})

CONFIG_FILE = Path(__file__).resolve().with_name("approved_repositories.txt")


def approved_repositories() -> frozenset[str]:
    raw = os.getenv("CONTROL_ALLOWED_REPOS", "").strip()
    if raw:
        return frozenset(item.strip() for item in raw.split(",") if item.strip())
    if CONFIG_FILE.exists():
        values = {
            line.strip()
            for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        if values:
            return frozenset(values)
    return DEFAULT_APPROVED_REPOSITORIES


def is_approved_repository(repo: str) -> bool:
    return repo.strip() in approved_repositories()
