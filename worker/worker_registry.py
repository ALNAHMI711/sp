#!/usr/bin/env python3
"""Durable worker liveness registry for the control plane."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkerRegistry:
    def __init__(self, database: str | Path, stale_after_seconds: int = 90) -> None:
        if stale_after_seconds < 1:
            raise ValueError("stale_after_seconds must be positive")
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.stale_after_seconds = stale_after_seconds
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
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    hostname TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'online',
                    last_seen TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_workers_last_seen ON workers(last_seen)")

    def heartbeat(self, worker_id: str, hostname: str = "", version: str = "") -> dict:
        worker_id, hostname, version = worker_id.strip(), hostname.strip(), version.strip()
        if not worker_id:
            raise ValueError("worker_id is required")
        stamp = now()
        with self._db() as db:
            db.execute(
                """INSERT INTO workers(worker_id,hostname,version,status,last_seen,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(worker_id) DO UPDATE SET
                     hostname=excluded.hostname, version=excluded.version,
                     status='online', last_seen=excluded.last_seen,
                     updated_at=excluded.updated_at""",
                (worker_id, hostname, version, "online", stamp, stamp),
            )
        return self.get(worker_id)

    def refresh_statuses(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.stale_after_seconds)
        stamp = now()
        with self._db() as db:
            changed = db.execute(
                """UPDATE workers SET status='stale', updated_at=?
                   WHERE status='online' AND last_seen < ?""",
                (stamp, cutoff.isoformat()),
            )
        return changed.rowcount

    def get(self, worker_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM workers WHERE worker_id=?", (worker_id,)).fetchone()
        return dict(row) if row else None

    def list(self) -> list[dict]:
        self.refresh_statuses()
        with self._db() as db:
            rows = db.execute("SELECT * FROM workers ORDER BY worker_id").fetchall()
        return [dict(row) for row in rows]

    def ping(self) -> bool:
        with self._db() as db:
            db.execute("SELECT 1").fetchone()
        return True
