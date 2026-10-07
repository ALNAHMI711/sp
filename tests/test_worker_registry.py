from datetime import datetime, timedelta, timezone

from worker.worker_registry import WorkerRegistry


def test_heartbeat_registers_worker(tmp_path):
    registry = WorkerRegistry(tmp_path / "workers.sqlite3")
    row = registry.heartbeat("worker-a", "node-a", "1.0")
    assert row["status"] == "online"
    assert row["hostname"] == "node-a"
    assert registry.list()[0]["worker_id"] == "worker-a"


def test_stale_worker_is_detected(tmp_path):
    registry = WorkerRegistry(tmp_path / "workers.sqlite3", stale_after_seconds=30)
    registry.heartbeat("worker-a")
    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with registry._db() as db:
        db.execute("UPDATE workers SET last_seen=? WHERE worker_id=?", (old, "worker-a"))
    assert registry.refresh_statuses() == 1
    assert registry.get("worker-a")["status"] == "stale"


def test_heartbeat_recovers_stale_worker(tmp_path):
    registry = WorkerRegistry(tmp_path / "workers.sqlite3", stale_after_seconds=30)
    registry.heartbeat("worker-a")
    with registry._db() as db:
        db.execute(
            "UPDATE workers SET status='stale', last_seen=? WHERE worker_id=?",
            ((datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), "worker-a"),
        )
    row = registry.heartbeat("worker-a", "node-a", "2.0")
    assert row["status"] == "online"
    assert row["version"] == "2.0"
