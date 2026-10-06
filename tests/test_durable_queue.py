from worker.durable_queue import DurableJobQueue


def test_enqueue_claim_complete_roundtrip(tmp_path):
    queue = DurableJobQueue(tmp_path / "queue.db")
    queued = queue.enqueue("job-1", {"task": "inspect"})
    assert queued["status"] == "queued"
    claimed = queue.claim()
    assert claimed is not None
    assert claimed["id"] == "job-1"
    assert claimed["attempts"] == 1
    assert queue.complete("job-1")["status"] == "completed"
    assert queue.get("job-1")["status"] == "completed"


def test_stale_running_job_is_recovered(tmp_path):
    queue = DurableJobQueue(tmp_path / "queue.db")
    queue.enqueue("job-2", {"task": "retry"})
    claimed = queue.claim()
    assert claimed is not None
    with queue._connect() as conn:
        conn.execute(
            "UPDATE jobs SET claimed_at=?, updated_at=? WHERE id='job-2'",
            ("2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00"),
        )
    assert queue.recover_stale(60) == 1
    assert queue.get("job-2")["status"] == "queued"


def test_retry_keeps_job_durable(tmp_path):
    queue = DurableJobQueue(tmp_path / "queue.db")
    queue.enqueue("job-3", {"task": "retry"})
    queue.claim()
    retry_at = "2999-01-01T00:00:00+00:00"
    result = queue.fail("job-3", "temporary", retry_at=retry_at)
    assert result["status"] == "queued"
    assert result["error"] == "temporary"
