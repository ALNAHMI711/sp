#!/usr/bin/env python3
"""PostgreSQL-backed worker liveness registry."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row


def now() -> datetime:
    return datetime.now(timezone.utc)


class PostgresWorkerRegistry:
    def __init__(self, dsn: str, stale_after_seconds: int = 90) -> None:
        if not dsn.strip():
            raise ValueError("PostgreSQL DSN is required")
        if stale_after_seconds < 1:
            raise ValueError("stale_after_seconds must be positive")
        self.dsn = dsn
        self.stale_after_seconds = stale_after_seconds

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def heartbeat(self, worker_id: str, hostname: str = "", version: str = "") -> dict:
        worker_id, hostname, version = worker_id.strip(), hostname.strip(), version.strip()
        if not worker_id:
            raise ValueError("worker_id is required")
        stamp = now()
        with self._connect() as db:
            row = db.execute(
                """INSERT INTO workers(worker_id,hostname,version,status,last_seen,updated_at)
                   VALUES(%s,%s,%s,'online',%s,%s)
                   ON CONFLICT(worker_id) DO UPDATE SET
                     hostname=EXCLUDED.hostname, version=EXCLUDED.version,
                     status='online', last_seen=EXCLUDED.last_seen,
                     updated_at=EXCLUDED.updated_at
                   RETURNING *""",
                (worker_id, hostname, version, stamp, stamp),
            ).fetchone()
        return dict(row)

    def refresh_statuses(self) -> int:
        cutoff = now() - timedelta(seconds=self.stale_after_seconds)
        with self._connect() as db:
            result = db.execute(
                """UPDATE workers SET status='stale', updated_at=%s
                   WHERE status='online' AND last_seen < %s""",
                (now(), cutoff),
            )
        return result.rowcount

    def get(self, worker_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM workers WHERE worker_id=%s", (worker_id,)).fetchone()
        return dict(row) if row else None

    def list(self) -> list[dict]:
        self.refresh_statuses()
        with self._connect() as db:
            rows = db.execute("SELECT * FROM workers ORDER BY worker_id").fetchall()
        return [dict(row) for row in rows]

    def ping(self) -> bool:
        with self._connect() as db:
            db.execute("SELECT 1").fetchone()
        return True
