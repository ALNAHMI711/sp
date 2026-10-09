#!/usr/bin/env python3
"""Apply control-plane PostgreSQL schema migrations."""
from __future__ import annotations

import os

import psycopg


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    target_repo TEXT NOT NULL,
    task TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_approval',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    worker_id TEXT,
    lease_token TEXT,
    lease_until TIMESTAMPTZ,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status, lease_until);

CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'online',
    last_seen TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workers_last_seen ON workers(last_seen);
"""


def main() -> None:
    dsn = os.environ.get("CONTROL_POSTGRES_DSN", "").strip()
    if not dsn:
        raise SystemExit("CONTROL_POSTGRES_DSN is required to apply PostgreSQL migrations.")

    with psycopg.connect(dsn) as db:
        with db.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute("ALTER TABLE jobs ALTER COLUMN status SET DEFAULT 'pending_approval'")
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS lease_token TEXT")
            cur.execute(
                "UPDATE jobs SET status='pending_approval', updated_at=NOW() WHERE status='queued'"
            )
            cur.execute(
                "INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING",
                ("0001_control_queue",),
            )
            cur.execute(
                "INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING",
                ("0002_job_lease_token",),
            )
    print("PostgreSQL schema migrations 0001_control_queue and 0002_job_lease_token applied.")


if __name__ == "__main__":
    main()
