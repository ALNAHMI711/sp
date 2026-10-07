import os

import pytest

from worker.postgres_worker_registry import PostgresWorkerRegistry


DSN = os.getenv("CONTROL_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="CONTROL_POSTGRES_DSN is required")


@pytest.fixture()
def registry():
    value = PostgresWorkerRegistry(DSN, stale_after_seconds=30)
    with value._connect() as db:
        db.execute("TRUNCATE TABLE workers")
    return value


def test_postgres_worker_heartbeat_registers_worker(registry):
    row = registry.heartbeat("worker-pg-a", "node-a", "1.0")
    assert row["worker_id"] == "worker-pg-a"
    assert row["hostname"] == "node-a"
    assert row["version"] == "1.0"
    assert row["status"] == "online"
    assert registry.get("worker-pg-a")["status"] == "online"


def test_postgres_worker_stale_detection(registry):
    registry.heartbeat("worker-pg-stale", "node-a", "1.0")
    with registry._connect() as db:
        db.execute(
            "UPDATE workers SET last_seen=NOW() - INTERVAL '1 minute' "
            "WHERE worker_id=%s",
            ("worker-pg-stale",),
        )
    assert registry.refresh_statuses() == 1
    assert registry.get("worker-pg-stale")["status"] == "stale"


def test_postgres_worker_heartbeat_recovers_stale_worker(registry):
    registry.heartbeat("worker-pg-recover", "node-a", "1.0")
    with registry._connect() as db:
        db.execute(
            "UPDATE workers SET last_seen=NOW() - INTERVAL '1 minute', status='stale' "
            "WHERE worker_id=%s",
            ("worker-pg-recover",),
        )
    row = registry.heartbeat("worker-pg-recover", "node-b", "2.0")
    assert row["status"] == "online"
    assert row["hostname"] == "node-b"
    assert row["version"] == "2.0"


def test_postgres_worker_ping(registry):
    assert registry.ping() is True
