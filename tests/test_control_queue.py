import sqlite3
from pathlib import Path

from worker.control_queue import ControlQueue


def test_idempotency_and_recovery(tmp_path: Path) -> None:
    queue = ControlQueue(tmp_path / "queue.sqlite3")
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "same-task")
    try:
        queue.enqueue("ALNAHMI711/sp", "run tests", "read_only", "same-task")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("duplicate idempotency key must be rejected")

    claimed = queue.claim("worker-1", lease_seconds=1)
    assert claimed and claimed["job_id"] == job_id

    with queue._db() as db:
        db.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00+00:00' WHERE job_id=?",
            (job_id,),
        )

    assert queue.recover_expired() == 1
    claimed_again = queue.claim("worker-2", lease_seconds=60)
    assert claimed_again and claimed_again["job_id"] == job_id
    queue.finish(job_id, True)

    with queue._db() as db:
        row = db.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    assert row["status"] == "succeeded"
