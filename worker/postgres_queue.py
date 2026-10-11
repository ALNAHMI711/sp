#!/usr/bin/env python3
"""PostgreSQL queue adapter for multi-worker production deployments.

Lifecycle semantics intentionally mirror ControlQueue. Claiming uses
FOR UPDATE SKIP LOCKED so multiple workers can consume the queue without
claiming the same job.
"""
from __future__ import annotations

import re
import uuid
import secrets
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from worker.repo_policy import approved_repositories

SENSITIVE_TASK = re.compile(
    r"(LIVE|live trading|withdrawal|withdrawals|secret rotation|rotate secret|"
    r"production deploy|production deployment|delete repository|drop database|"
    r"force push|liquidat(e|ion))",
    re.IGNORECASE,
)

SCHEMA = """
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
"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def validate_task(target_repo: str, task: str, mode: str) -> None:
    if target_repo not in approved_repositories():
        raise PermissionError("repository is not in the approved initial set")
    if SENSITIVE_TASK.search(task):
        raise PermissionError("sensitive task requires explicit approval")
    if mode not in {"read_only", "propose_changes"}:
        raise ValueError("invalid mode")


class PostgresQueue:
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("PostgreSQL DSN is required")
        self.dsn = dsn

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def init(self) -> None:
        with self._connect() as db:
            with db.cursor() as cur:
                cur.execute(SCHEMA)

    def close(self) -> None:
        """Connection-per-operation adapter; kept for backend interface symmetry."""
        return None

    def ping(self) -> bool:
        with self._connect() as db:
            db.execute("SELECT 1").fetchone()
        return True

    def enqueue(self, target_repo: str, task: str, mode: str,
                idempotency_key: str | None = None,
                max_attempts: int = 3) -> str:
        target_repo, task = target_repo.strip(), task.strip()
        if not target_repo or not task:
            raise ValueError("target_repo and task are required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        validate_task(target_repo, task, mode)
        key = idempotency_key or str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        stamp = now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO jobs
                   (job_id,idempotency_key,target_repo,task,mode,max_attempts,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (job_id, key, target_repo, task, mode, max_attempts, stamp, stamp),
            )
        return job_id

    def approve(self, job_id: str) -> bool:
        with self._connect() as db:
            result = db.execute(
                "UPDATE jobs SET status='queued', updated_at=%s WHERE job_id=%s AND status='pending_approval'",
                (now(), job_id),
            )
        return result.rowcount == 1

    def claim(self, worker_id: str, lease_seconds: int = 900) -> dict | None:
        if not worker_id.strip() or lease_seconds < 1:
            raise ValueError("worker_id and positive lease_seconds are required")
        stamp, lease = now(), now() + timedelta(seconds=lease_seconds)
        lease_token = secrets.token_urlsafe(32)
        with self._connect() as db:
            row = db.execute(
                """SELECT * FROM jobs
                   WHERE status='queued'
                   ORDER BY created_at, job_id
                   FOR UPDATE SKIP LOCKED
                   LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            claimed = db.execute(
                """UPDATE jobs SET status='running', attempts=attempts+1,
                   worker_id=%s, lease_token=%s, lease_until=%s, updated_at=%s
                   WHERE job_id=%s AND status='queued'
                   RETURNING *""",
                (worker_id, lease_token, lease, stamp, row["job_id"]),
            ).fetchone()
            return dict(claimed) if claimed else None

    def renew_lease(self, job_id: str, worker_id: str, lease_seconds: int = 900, lease_token: str | None = None) -> bool:
        if not worker_id or not lease_token:
            raise ValueError("worker_id and lease_token are required to renew a lease")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        lease = now() + timedelta(seconds=lease_seconds)
        with self._connect() as db:
            result = db.execute(
                """UPDATE jobs SET lease_until=%s, updated_at=%s
                   WHERE job_id=%s AND worker_id=%s AND status='running' AND lease_token=%s""",
                (lease, now(), job_id, worker_id, lease_token),
            )
        return result.rowcount == 1

    def finish(self, job_id: str, success: bool, error: str = "", worker_id: str | None = None, lease_token: str | None = None) -> bool:
        if not worker_id or not lease_token:
            raise ValueError("worker_id and lease_token are required to finish a job")
        status = "succeeded" if success else "failed"
        with self._connect() as db:
            result = db.execute(
                """UPDATE jobs SET status=%s, worker_id=NULL, lease_token=NULL, lease_until=NULL,
                   last_error=%s, updated_at=%s
                   WHERE job_id=%s AND worker_id=%s AND status='running' AND lease_token=%s""",
                (status, error[:2000], now(), job_id, worker_id, lease_token),
            )
        return result.rowcount == 1

    def cancel(self, job_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                """UPDATE jobs SET
                   status=CASE status
                     WHEN 'pending_approval' THEN 'cancelled'
                     WHEN 'queued' THEN 'cancelled'
                     WHEN 'running' THEN 'cancel_requested'
                     ELSE status END,
                   updated_at=%s
                   WHERE job_id=%s
                   RETURNING status""",
                (now(), job_id),
            ).fetchone()
        return row["status"] if row else None

    def mark_cancelled(self, job_id: str, reason: str = "cancelled") -> bool:
        with self._connect() as db:
            result = db.execute(
                """UPDATE jobs SET status='cancelled', worker_id=NULL, lease_token=NULL,
                   lease_until=NULL, last_error=%s, updated_at=%s
                   WHERE job_id=%s AND status='cancel_requested'""",
                (reason[:2000], now(), job_id),
            )
        return result.rowcount == 1

    def recover_expired(self) -> int:
        stamp = now()
        with self._connect() as db:
            result = db.execute(
                """UPDATE jobs SET
                   status=CASE WHEN attempts < max_attempts THEN 'queued' ELSE 'failed' END,
                   worker_id=NULL, lease_until=NULL,
                   last_error='worker_lease_expired', updated_at=%s
                   WHERE status='running' AND lease_until IS NOT NULL AND lease_until<=%s""",
                (stamp, stamp),
            )
        return result.rowcount

    def request_kill_switch(self, reason: str = "kill_switch") -> dict:
        stamp = now()
        with self._connect() as db:
            queued = db.execute(
                """UPDATE jobs SET status='cancelled', last_error=%s, updated_at=%s
                   WHERE status IN ('pending_approval', 'queued')""", (reason[:2000], stamp)
            ).rowcount
            running = db.execute(
                """UPDATE jobs SET status='cancel_requested', last_error=%s, updated_at=%s
                   WHERE status='running'""", (reason[:2000], stamp)
            ).rowcount
        return {"queued_cancelled": queued, "running_cancel_requested": running}

    def get(self, job_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,)).fetchone()
        return dict(row) if row else None
