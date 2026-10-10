import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from worker.postgres_queue import PostgresQueue


DSN = os.getenv("CONTROL_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="CONTROL_POSTGRES_DSN is required")


@pytest.fixture()
def queue():
    q = PostgresQueue(DSN)
    q.init()
    with q._connect() as db:
        db.execute("TRUNCATE TABLE jobs")
    return q


def test_postgres_queue_lifecycle(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-lifecycle")
    assert queue.approve(job_id)
    job = queue.claim("worker-a")
    assert job and job["job_id"] == job_id
    assert queue.finish(job_id, True, worker_id="worker-a", lease_token=job["lease_token"])
    assert queue.get(job_id)["status"] == "succeeded"


def test_postgres_queue_idempotency(queue):
    queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-idempotent")
    with pytest.raises(Exception):
        queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-idempotent")


def test_postgres_two_workers_claim_distinct_jobs(queue):
    first = queue.enqueue("ALNAHMI711/sp", "job one", "read_only", "pg-worker-1")
    second = queue.enqueue("ALNAHMI711/sp", "job two", "read_only", "pg-worker-2")
    assert queue.approve(first)
    assert queue.approve(second)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda wid: queue.claim(wid), ("worker-a", "worker-b")))
    ids = {row["job_id"] for row in claimed if row}
    assert len(ids) == 2


def test_postgres_cancel_cannot_be_overwritten(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-cancel")
    assert queue.approve(job_id)
    queue.claim("worker-a")
    assert queue.cancel(job_id) == "cancel_requested"
    current = queue.get(job_id)
    assert queue.finish(job_id, True, worker_id="worker-a", lease_token=current["lease_token"]) is False
    assert queue.mark_cancelled(job_id, "user_cancel") is True
    assert queue.get(job_id)["status"] == "cancelled"



def test_postgres_kill_switch_cancels_pending_approval(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-kill-pending")
    result = queue.request_kill_switch("emergency")
    assert result["queued_cancelled"] == 1
    assert result["running_cancel_requested"] == 0
    assert queue.get(job_id)["status"] == "cancelled"

def test_postgres_expired_lease_recovery(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-recovery")
    assert queue.approve(job_id)
    queue.claim("worker-a", lease_seconds=1)
    with queue._connect() as db:
        db.execute(
            "UPDATE jobs SET lease_until=NOW() - INTERVAL '1 second' WHERE job_id=%s",
            (job_id,),
        )
    assert queue.recover_expired() == 1
    assert queue.get(job_id)["status"] == "queued"


def test_postgres_renew_lease_keeps_active_job_owned(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-renew")
    assert queue.approve(job_id)
    claimed = queue.claim("worker-a", lease_seconds=1)
    assert claimed
    assert queue.renew_lease(job_id, "worker-a", lease_seconds=60, lease_token=claimed["lease_token"]) is True
    current = queue.get(job_id)
    assert current["worker_id"] == "worker-a"
    assert current["status"] == "running"

def test_postgres_expired_worker_cannot_finish_after_recovery(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-lease-handoff")
    assert queue.approve(job_id)
    assert queue.claim("worker-a", lease_seconds=1)
    with queue._connect() as db:
        db.execute(
            "UPDATE jobs SET lease_until=NOW() - INTERVAL '1 second' WHERE job_id=%s",
            (job_id,),
        )
    assert queue.recover_expired() == 1
    reclaimed = queue.claim("worker-b", lease_seconds=60)
    assert reclaimed and reclaimed["job_id"] == job_id
    assert queue.finish(job_id, True, worker_id="worker-b", lease_token=reclaimed["lease_token"]) is True
    assert queue.finish(job_id, False, "stale-worker", worker_id="worker-a", lease_token="stale") is False
    assert queue.renew_lease(job_id, "worker-a", lease_seconds=60) is False


def test_postgres_recovered_job_cancellation_blocks_late_worker(queue):
    job_id = queue.enqueue(
        "ALNAHMI711/sp", "run tests", "read_only", "pg-recovery-cancel"
    )
    assert queue.approve(job_id)
    assert queue.claim("worker-a", lease_seconds=1)
    with queue._connect() as db:
        db.execute(
            "UPDATE jobs SET lease_until=NOW() - INTERVAL '1 second' WHERE job_id=%s",
            (job_id,),
        )
    assert queue.recover_expired() == 1
    reclaimed = queue.claim("worker-b", lease_seconds=60)
    assert reclaimed and reclaimed["job_id"] == job_id
    assert queue.cancel(job_id) == "cancel_requested"
    assert queue.finish(job_id, True, worker_id="worker-b", lease_token=reclaimed["lease_token"]) is False
    assert queue.mark_cancelled(job_id, "recovered_job_cancelled") is True
    assert queue.finish(job_id, False, "stale-worker", worker_id="worker-a", lease_token="stale") is False
    assert queue.renew_lease(job_id, "worker-a", lease_seconds=60) is False
    assert queue.get(job_id)["status"] == "cancelled"


def test_postgres_wrong_worker_cannot_finish_active_job(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-finish-owner")
    assert queue.approve(job_id)
    assert queue.claim("worker-a", lease_seconds=60)
    assert queue.finish(job_id, True, worker_id="worker-b", lease_token="wrong") is False
    assert queue.get(job_id)["status"] == "running"
    assert queue.finish(job_id, True, worker_id="worker-a", lease_token=queue.get(job_id)["lease_token"]) is True

def test_postgres_missing_lease_token_cannot_renew_or_finish(queue):
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "pg-missing-lease-token")
    assert queue.approve(job_id)
    claimed = queue.claim("worker-a", lease_seconds=60)
    assert claimed and claimed["job_id"] == job_id

    assert queue.renew_lease(job_id, "worker-a", lease_seconds=60) is False
    assert queue.finish(job_id, True, worker_id="worker-a") is False
    current = queue.get(job_id)
    assert current["status"] == "running"
    assert current["lease_token"] == claimed["lease_token"]

