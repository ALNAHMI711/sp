from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DurableJobQueue:
    """Restart-safe, SQLite-backed job queue for the control plane."""

    TERMINAL = {"completed", "failed", "cancelled"}

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.database_path), timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT NOT NULL,
                    claimed_at TEXT,
                    updated_at TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(status, available_at, updated_at)"
            )

    def enqueue(
        self,
        job_id: str,
        payload: dict[str, Any],
        *,
        available_at: str | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        ready = available_at or now
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(id, payload, status, attempts, available_at, updated_at)
                VALUES (?, ?, 'queued', 0, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload=excluded.payload,
                    status=CASE
                        WHEN jobs.status IN ('completed', 'cancelled') THEN jobs.status
                        ELSE 'queued'
                    END,
                    available_at=excluded.available_at,
                    claimed_at=NULL,
                    updated_at=excluded.updated_at,
                    error=''
                """,
                (job_id, encoded, ready, now),
            )
            return self._row(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def claim(self) -> dict[str, Any] | None:
        now = self._now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status='queued' AND available_at<=?
                ORDER BY updated_at ASC, id ASC
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            changed = conn.execute(
                """
                UPDATE jobs
                SET status='running', attempts=attempts+1,
                    claimed_at=?, updated_at=?
                WHERE id=? AND status='queued'
                """,
                (now, now, row["id"]),
            )
            if changed.rowcount != 1:
                conn.rollback()
                return None
            claimed = conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            conn.commit()
            return self._row(claimed)

    def recover_stale(self, max_age_seconds: int = 300) -> int:
        if max_age_seconds < 1:
            raise ValueError("max_age_seconds must be positive")
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_seconds
        now = self._now()
        recovered = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, claimed_at FROM jobs WHERE status='running' AND claimed_at IS NOT NULL"
            ).fetchall()
            for row in rows:
                try:
                    stamp = datetime.fromisoformat(row["claimed_at"]).timestamp()
                except (TypeError, ValueError):
                    stamp = 0
                if stamp <= cutoff:
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status='queued', available_at=?, claimed_at=NULL,
                            updated_at=?, error='recovered_after_restart'
                        WHERE id=? AND status='running'
                        """,
                        (now, now, row["id"]),
                    )
                    recovered += 1
        return recovered

    def complete(self, job_id: str) -> dict[str, Any] | None:
        return self._transition(job_id, "completed", "")

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        return self._transition(job_id, "cancelled", "")

    def fail(self, job_id: str, error: str, retry_at: str | None = None) -> dict[str, Any] | None:
        now = self._now()
        with self._connect() as conn:
            if retry_at:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status='queued', available_at=?, claimed_at=NULL,
                        updated_at=?, error=?
                    WHERE id=? AND status='running'
                    """,
                    (retry_at, now, error[:2000], job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status='failed', claimed_at=NULL, updated_at=?, error=?
                    WHERE id=? AND status='running'
                    """,
                    (now, error[:2000], job_id),
                )
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._row(row) if row else None

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._row(row) if row else None

    @staticmethod
    def _transition(job_id: str, status: str, error: str) -> dict[str, Any] | None:
        raise RuntimeError("_transition requires an instance")

    def _transition(self, job_id: str, status: str, error: str) -> dict[str, Any] | None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs SET status=?, claimed_at=NULL, updated_at=?, error=?
                WHERE id=? AND status='running'
                """,
                (status, now, error, job_id),
            )
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._row(row) if row else None

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        result = dict(row)
        try:
            result["payload"] = json.loads(result["payload"])
        except (TypeError, ValueError):
            result["payload"] = {}
        return result
