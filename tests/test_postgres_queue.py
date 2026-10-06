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
    assert queue.finish(job_id, True)
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
    assert queue.finish(job_id, True) is False
    assert queue.mark_cancelled(job_id, "user_cancel") is True
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
