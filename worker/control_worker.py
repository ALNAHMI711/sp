#!/usr/bin/env python3
"""Single-node autonomous control worker.

The worker owns orchestration, not authorization. Every job has already passed
queue admission, and policy is re-checked before OpenHands is started.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from control_queue import ControlQueue


ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], *, env: dict[str, str], timeout: int | None = None) -> int:
    return subprocess.run(cmd, cwd=ROOT, env=env, timeout=timeout, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=".data/control-queue.sqlite3")
    parser.add_argument("--worker-id", default=f"worker-{uuid.uuid4()}")
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()

    queue = ControlQueue(args.db)
    queue.recover_expired()

    while True:
        job = queue.claim(args.worker_id, args.lease_seconds)
        if job is None:
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
            queue.recover_expired()
            continue

        workspace = Path(tempfile.mkdtemp(prefix=f"autonomous-{job['job_id']}-"))
        env = os.environ.copy()
        env.update({
            "TARGET_REPO": job["target_repo"],
            "TASK": job["task"],
            "WRITE_MODE": job["mode"],
            "OPENHANDS_WORKING_DIR": str(workspace),
            "OPENHANDS_TASK": job["task"],
            "INSPECTION_WORKDIR": str(workspace),
        })

        try:
            policy_rc = run(["bash", str(ROOT / "worker/policy.sh")], env=env)
            if policy_rc != 0:
                queue.finish(job["job_id"], False, "policy_blocked")
                continue

            inspect_rc = run(["bash", str(ROOT / "worker/inspect.sh")], env=env)
            if inspect_rc != 0:
                queue.finish(job["job_id"], False, "inspection_failed")
                continue

            if job["mode"] == "propose_changes":
                if not os.environ.get("OPENHANDS_AGENT_SERVER_URL") or not os.environ.get("OPENHANDS_SESSION_API_KEY"):
                    queue.finish(job["job_id"], False, "openhands_not_configured")
                    continue
                rc = run(["bash", str(ROOT / "worker/openhands-run.sh")], env=env, timeout=args.lease_seconds)
                if rc != 0:
                    queue.finish(job["job_id"], False, f"openhands_failed:{rc}")
                    continue

            test_rc = run(["bash", str(ROOT / "worker/test.sh"), str(workspace)], env=env)
            if test_rc != 0:
                queue.finish(job["job_id"], False, "tests_failed")
                continue

            completion_env = env | {"OPENHANDS_STATUS": "finished" if job["mode"] == "propose_changes" else "not_requested"}
            completion_rc = run(["bash", str(ROOT / "worker/completion.sh"), str(workspace)], env=completion_env)
            if completion_rc != 0:
                queue.finish(job["job_id"], False, "completion_gate_failed")
                continue

            queue.finish(job["job_id"], True)
        except subprocess.TimeoutExpired:
            queue.finish(job["job_id"], False, "worker_timeout")
        except Exception as exc:
            queue.finish(job["job_id"], False, f"worker_exception:{type(exc).__name__}")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
