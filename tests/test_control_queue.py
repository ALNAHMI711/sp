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


def test_policy_is_enforced_at_queue_boundary(tmp_path: Path) -> None:
    queue = ControlQueue(tmp_path / "queue.sqlite3")
    import pytest
    with pytest.raises(PermissionError):
        queue.enqueue("unknown/repo", "run tests", "read_only")
    with pytest.raises(PermissionError):
        queue.enqueue("ALNAHMI711/sp", "enable LIVE trading", "propose_changes")


def test_cancel_states(tmp_path: Path) -> None:
    queue = ControlQueue(tmp_path / "queue.sqlite3")
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only")
    assert queue.cancel(job_id) == "cancelled"
    assert queue.get(job_id)["status"] == "cancelled"
    job2 = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only")
    queue.claim("worker-1", lease_seconds=60)
    assert queue.cancel(job2) == "cancel_requested"
    assert queue.get(job2)["status"] == "cancel_requested"


def test_cancel_requested_is_finalized(tmp_path: Path) -> None:
    queue = ControlQueue(tmp_path / "queue.sqlite3")
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only")
    queue.claim("worker-1", lease_seconds=60)
    assert queue.cancel(job_id) == "cancel_requested"
    assert queue.mark_cancelled(job_id, "test_cancel") is True
    assert queue.get(job_id)["status"] == "cancelled"


def test_kill_switch_marks_queued_and_running_jobs(tmp_path: Path) -> None:
    queue = ControlQueue(tmp_path / "queue.sqlite3")
    running = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only")
    queued = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only")
    queue.claim("worker-1", lease_seconds=60)
    result = queue.request_kill_switch()
    assert result == {"queued_cancelled": 1, "running_cancel_requested": 1}
    assert queue.get(queued)["status"] == "cancelled"
    assert queue.get(running)["status"] == "cancel_requested"

def test_finish_cannot_override_cancel_request(tmp_path: Path) -> None:
    queue = ControlQueue(tmp_path / "queue.sqlite3")
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only")
    queue.claim("worker-1", lease_seconds=60)
    assert queue.cancel(job_id) == "cancel_requested"
    assert queue.finish(job_id, True) is False
    assert queue.get(job_id)["status"] == "cancel_requested"
    assert queue.mark_cancelled(job_id, "cancelled_before_finish") is True
    assert queue.get(job_id)["status"] == "cancelled"

def test_cancel_is_idempotent_for_active_job(tmp_path: Path) -> None:
    queue = ControlQueue(tmp_path / "queue.sqlite3")
    job_id = queue.enqueue("ALNAHMI711/sp", "run tests", "read_only")
    queue.claim("worker-1", lease_seconds=60)
    assert queue.cancel(job_id) == "cancel_requested"
    assert queue.cancel(job_id) == "cancel_requested"
    assert queue.get(job_id)["status"] == "cancel_requested"
