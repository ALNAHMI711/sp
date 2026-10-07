#!/usr/bin/env python3
"""Liveness/readiness probe for the worker container."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    backend = os.getenv("CONTROL_QUEUE_BACKEND", "sqlite").strip().lower()

    try:
        if backend == "sqlite":
            db = Path(os.environ.get("CONTROL_QUEUE_DB", "/app/data/control-queue.sqlite3"))
            db.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db, timeout=3) as conn:
                conn.execute("SELECT 1").fetchone()
        elif backend == "postgres":
            dsn = os.getenv("CONTROL_POSTGRES_DSN", "").strip()
            if not dsn:
                raise RuntimeError("CONTROL_POSTGRES_DSN is required")
            import psycopg

            with psycopg.connect(dsn) as conn:
                conn.execute("SELECT 1").fetchone()
        else:
            raise RuntimeError(f"unsupported CONTROL_QUEUE_BACKEND: {backend}")
    except Exception as exc:
        print(f"worker unhealthy: {type(exc).__name__}", file=sys.stderr)
        return 1

    print("worker healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
