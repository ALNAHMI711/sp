#!/usr/bin/env python3
"""Minimal liveness/readiness probe for the worker container."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

db = Path(os.environ.get("CONTROL_QUEUE_DB", "/app/data/control-queue.sqlite3"))
try:
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db, timeout=3) as conn:
        conn.execute("SELECT 1").fetchone()
except Exception as exc:
    print(f"worker unhealthy: {type(exc).__name__}", file=sys.stderr)
    raise SystemExit(1)
print("worker healthy")
