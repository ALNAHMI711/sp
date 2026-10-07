from __future__ import annotations

import os
import threading
import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from control_worker import run


def test_run_interrupts_child_process_group() -> None:
    stop = threading.Event()
    timer = threading.Timer(0.3, stop.set)
    timer.start()
    started = time.monotonic()
    try:
        rc = run(
            ["bash", "-c", "sleep 60"],
            env=os.environ.copy(),
            should_stop=stop.is_set,
        )
    finally:
        timer.cancel()

    assert rc == 125
    assert time.monotonic() - started < 5


def test_request_cancellation_ignores_missing_job(tmp_path) -> None:
    from control_worker import request_cancellation

    class Queue:
        def get(self, job_id):
            return None

        def cancel(self, job_id):
            raise AssertionError("missing job must not be cancelled")

    kill_file = tmp_path / "KILL_SWITCH"
    kill_file.write_text("enabled\n")
    request_cancellation(Queue(), "missing", kill_file)
