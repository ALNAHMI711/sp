#!/usr/bin/env python3
"""Apply control-plane PostgreSQL schema migrations."""
from __future__ import annotations

import os
import psycopg

SCHEMA = "CREATE TABLE IF NOT EXISTS schema_migrations (\n    version TEXT PRIMARY KEY,\n    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n);\n\nCREATE TABLE IF NOT EXISTS jobs (\n    job_id TEXT PRIMARY KEY,\n    idempotency_key TEXT NOT NULL UNIQUE,\n    target_repo TEXT NOT NULL,\n    task TEXT NOT NULL,\n    mode TEXT NOT NULL,\n    status TEXT NOT NULL DEFAULT 'pending_approval',\n    attempts INTEGER NOT NULL DEFAULT 0,\n    max_attempts INTEGER NOT NULL DEFAULT 3,\n    worker_id TEXT,\n    lease_until TIMESTAMPTZ,\n    last_error TEXT NOT NULL DEFAULT '',\n    created_at TIMESTAMPTZ NOT NULL,\n    updated_at TIMESTAMPTZ NOT NULL\n);\n\nCREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(status, created_at);\nCREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status, lease_until);

-- Existing installations retain their current lifecycle; only new jobs use the approval gate.\n"

def main() -> None:
    dsn = os.environ["CONTROL_POSTGRES_DSN"].strip()
    if not dsn:
        print("PostgreSQL DSN not configured; migration skipped.")
        return
    with psycopg.connect(dsn) as db:
        with db.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute(
                "INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING",
                ("0001_control_queue",),
            )
    print("PostgreSQL schema migration 0001_control_queue applied.")

if __name__ == "__main__":
    main()
