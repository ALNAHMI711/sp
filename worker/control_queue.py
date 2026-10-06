#!/usr/bin/env python3
"""Small durable control-plane queue for autonomous jobs.

SQLite is the default single-node persistence layer. The API is deliberately
small so the storage implementation can later move to PostgreSQL without
changing lifecycle semantics.
"""
from __future__ import annotations

import argparse
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


APPROVED_REPOSITORIES = {
    "ALNAHMI711/Ahmed-Alnahmi-711",
    "ALNAHMI711/autonomous-business-manager",
    "ALNAHMI711/-",
    "ALNAHMI711/tte",
    "ALNAHMI711/sp",
}
SENSITIVE_TASK = __import__("re").compile(
    r"(LIVE|live trading|withdrawal|withdrawals|secret rotation|rotate secret|"
    r"production deploy|production deployment|delete repository|drop database|"
    r"force push|liquidat(e|ion))",
    __import__("re").IGNORECASE,
)


def validate_task(target_repo: str, task: str, mode: str) -> None:
    if target_repo not in APPROVED_REPOSITORIES:
        raise PermissionError("repository is not in the approved initial set")
    if SENSITIVE_TASK.search(task):
        raise PermissionError("sensitive task requires explicit approval")
    if mode not in {"read_only", "propose_changes"}:
        raise ValueError("invalid mode")


class ControlQueue:
    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _init(self) -> None:
        with self._db() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    target_repo TEXT NOT NULL,
                    task TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    worker_id TEXT,
                    lease_until TEXT,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(status, created_at)")

    def enqueue(self, target_repo: str, task: str, mode: str,
                idempotency_key: str | None = None,
                max_attempts: int = 3) -> str:
        if not target_repo.strip() or not task.strip():
            raise ValueError("target_repo and task are required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        validate_task(target_repo.strip(), task.strip(), mode)
        key = idempotency_key or str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        stamp = now()
        with self._db() as db:
            db.execute(
                """INSERT INTO jobs
                   (job_id,idempotency_key,target_repo,task,mode,max_attempts,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (job_id, key, target_repo.strip(), task.strip(), mode, max_attempts, stamp, stamp),
            )
        return job_id

    def claim(self, worker_id: str, lease_seconds: int = 900) -> dict | None:
        if not worker_id.strip() or lease_seconds < 1:
            raise ValueError("worker_id and positive lease_seconds are required")
        stamp = now()
        lease = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                db.commit()
                return None
            changed = db.execute(
                """UPDATE jobs SET status='running', attempts=attempts+1,
                   worker_id=?, lease_until=?, updated_at=?
                   WHERE job_id=? AND status='queued'""",
                (worker_id, lease, stamp, row["job_id"]),
            )
            if changed.rowcount != 1:
                db.rollback()
                return None
            claimed = db.execute("SELECT * FROM jobs WHERE job_id=?", (row["job_id"],)).fetchone()
            db.commit()
        return dict(claimed)

    def recover_expired(self) -> int:
        stamp = now()
        recovered = 0
        with self._db() as db:
            rows = db.execute(
                "SELECT job_id,attempts,max_attempts FROM jobs WHERE status='running' AND lease_until IS NOT NULL AND lease_until<=?",
                (stamp,),
            ).fetchall()
            for row in rows:
                status = "queued" if row["attempts"] < row["max_attempts"] else "failed"
                db.execute(
                    """UPDATE jobs SET status=?, worker_id=NULL, lease_until=NULL,
                       last_error=?, updated_at=? WHERE job_id=? AND status='running'""",
                    (status, "worker_lease_expired", stamp, row["job_id"]),
                )
                recovered += 1
        return recovered

    def finish(self, job_id: str, success: bool, error: str = "") -> None:
        status = "succeeded" if success else "failed"
        with self._db() as db:
            db.execute(
                """UPDATE jobs SET status=?, worker_id=NULL, lease_until=NULL,
                   last_error=?, updated_at=? WHERE job_id=? AND status='running'""",
                (status, error[:2000], now(), job_id),
            )

    def get(self, job_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def cancel(self, job_id: str) -> str | None:
        with self._db() as db:
            row = db.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return None
            target = "cancelled" if row["status"] == "queued" else ("cancel_requested" if row["status"] == "running" else row["status"])
            db.execute("UPDATE jobs SET status=?, updated_at=? WHERE job_id=?", (target, now(), job_id))
            return target


    def request_kill_switch(self, reason: str = "kill_switch") -> dict:
        stamp = now()
        with self._db() as db:
            queued = db.execute(
                "UPDATE jobs SET status='cancelled', last_error=?, updated_at=? WHERE status='queued'",
                (reason[:2000], stamp),
            ).rowcount
            running = db.execute(
                "UPDATE jobs SET status='cancel_requested', last_error=?, updated_at=? WHERE status='running'",
                (reason[:2000], stamp),
            ).rowcount
        return {"queued_cancelled": queued, "running_cancel_requested": running}

    def mark_cancelled(self, job_id: str, reason: str = "cancelled") -> bool:
        with self._db() as db:
            changed = db.execute(
                """UPDATE jobs SET status='cancelled', worker_id=NULL, lease_until=NULL,
                   last_error=?, updated_at=? WHERE job_id=? AND status='cancel_requested'""",
                (reason[:2000], now(), job_id),
            )
            return changed.rowcount == 1
