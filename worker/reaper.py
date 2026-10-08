#!/usr/bin/env python3
"""Lease reaper for durable autonomous jobs.

The reaper is deliberately storage-only: it never executes a job. It converts
expired running leases back into queue state using the queue's compare-and-set
recovery operation, so multiple reapers can safely run concurrently.
"""
from __future__ import annotations

import argparse
import os
import time

from control_worker import build_queue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=".data/control-queue.sqlite3")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.getenv("CONTROL_REAPER_INTERVAL_SECONDS", "15")),
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be positive")

    queue = build_queue(args.db)
    while True:
        recovered = queue.recover_expired()
        if recovered:
            print(f"recovered_expired_jobs={recovered}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
