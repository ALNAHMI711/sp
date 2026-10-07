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
