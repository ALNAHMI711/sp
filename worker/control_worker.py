#!/usr/bin/env python3
"""Single-node autonomous control worker.

The worker owns orchestration, not authorization. Every job has already passed
queue admission, and policy is re-checked before OpenHands is started.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from control_queue import ControlQueue
from postgres_queue import PostgresQueue
from worker_registry import WorkerRegistry
from postgres_worker_registry import PostgresWorkerRegistry


def build_queue(db: str):
    backend = os.getenv("CONTROL_QUEUE_BACKEND", "sqlite").strip().lower()
    if backend == "sqlite":
        return ControlQueue(db)
    if backend == "postgres":
        dsn = os.getenv("CONTROL_POSTGRES_DSN", "").strip()
        if not dsn:
            raise RuntimeError("CONTROL_POSTGRES_DSN is required for postgres backend")
        # PostgreSQL schema ownership belongs to the migration service; workers only consume it.
        return PostgresQueue(dsn)
    raise RuntimeError(f"unsupported CONTROL_QUEUE_BACKEND: {backend}")


ROOT = Path(__file__).resolve().parent.parent


def run(
    cmd: list[str],
    *,
    env: dict[str, str],
    timeout: int | None = None,
    should_stop=None,
) -> int:
    """Run a child process that can be interrupted by cancellation or lease loss."""
    process = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        start_new_session=True,
    )
    started = time.monotonic()
    try:
        while True:
            rc = process.poll()
            if rc is not None:
                return rc
            if timeout is not None and time.monotonic() - started >= timeout:
                _terminate_process_group(process)
                raise subprocess.TimeoutExpired(cmd, timeout)
            if should_stop is not None and should_stop():
                _terminate_process_group(process)
                return 125
            time.sleep(0.5)
    finally:
        if process.poll() is None:
            _terminate_process_group(process)


def _terminate_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        process.wait(timeout=5)


def start_lease_heartbeat(queue, job_id: str, worker_id: str, lease_seconds: int, lease_token: str | None = None):
    stop = threading.Event()
    lost = threading.Event()
    interval = max(1, lease_seconds // 3)

    def heartbeat() -> None:
        while not stop.wait(interval):
            try:
                if not queue.renew_lease(job_id, worker_id, lease_seconds, lease_token):
                    lost.set()
                    return
            except Exception:
                lost.set()
                return

    thread = threading.Thread(target=heartbeat, name=f"lease-{job_id}", daemon=True)
    thread.start()
    return stop, thread, lost


def cancellation_requested(queue, job_id: str, kill_file: Path) -> bool:
    if kill_file.exists():
        return True
    row = queue.get(job_id)
    return row is None or row["status"] == "cancel_requested"


def request_cancellation(queue, job_id: str, kill_file: Path) -> None:
    """Request cancellation only while the job still exists and is active."""
    if not kill_file.exists():
        return
    row = queue.get(job_id)
    if row and row["status"] == "running":
        queue.cancel(job_id)


def cancel_and_continue(queue, job_id: str, reason: str) -> bool:
    row = queue.get(job_id)
    if row and row["status"] == "cancel_requested":
        queue.mark_cancelled(job_id, reason)
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=".data/control-queue.sqlite3")
    parser.add_argument("--worker-id", default=f"worker-{uuid.uuid4()}")
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument(
        "--openhands-timeout-seconds",
        type=int,
        default=int(os.getenv("CONTROL_OPENHANDS_TIMEOUT_SECONDS", "3600")),
        help="Maximum runtime for one OpenHands execution; 0 disables this stage timeout.",
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()

    if args.lease_seconds < 1:
        parser.error("--lease-seconds must be positive")
    if args.openhands_timeout_seconds < 0:
        parser.error("--openhands-timeout-seconds must be zero or positive")

    queue = build_queue(args.db)
    if os.getenv("CONTROL_QUEUE_BACKEND", "sqlite").strip().lower() == "postgres":
        registry = PostgresWorkerRegistry(os.environ["CONTROL_POSTGRES_DSN"])
    else:
        registry = WorkerRegistry(os.getenv("CONTROL_WORKER_REGISTRY_DB", str(Path(args.db).with_name("workers.sqlite3"))))
    worker_version = os.getenv("CONTROL_WORKER_VERSION", "0.1.0")
    registry.heartbeat(args.worker_id, os.uname().nodename, worker_version)
    kill_file = Path(os.getenv("CONTROL_KILL_SWITCH_FILE", ".data/KILL_SWITCH"))
    queue.recover_expired()

    while True:
        registry.heartbeat(args.worker_id, os.uname().nodename, worker_version)
        if kill_file.exists():
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
            queue.recover_expired()
            continue
        job = queue.claim(args.worker_id, args.lease_seconds)
        if job is None:
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
            queue.recover_expired()
            continue

        workspace = Path(tempfile.mkdtemp(prefix=f"autonomous-{job['job_id']}-"))
        repo_dir = workspace / "repo"
        env = os.environ.copy()
        env.update({
            "TARGET_REPO": job["target_repo"],
            "TASK": job["task"],
            "WRITE_MODE": job["mode"],
            "OPENHANDS_WORKING_DIR": str(repo_dir),
            "OPENHANDS_TASK": job["task"],
            "CONTROL_QUEUE_DB": args.db,
            "CONTROL_JOB_ID": job["job_id"],
            "CONTROL_KILL_SWITCH_FILE": str(kill_file),
            "INSPECTION_WORKDIR": str(workspace),
        })

        heartbeat_stop, heartbeat_thread, lease_lost = start_lease_heartbeat(queue, job["job_id"], args.worker_id, args.lease_seconds, job.get("lease_token"))
        def should_stop() -> bool:
            return cancellation_requested(queue, job["job_id"], kill_file) or lease_lost.is_set()

        def lease_loss_requested() -> bool:
            return lease_lost.is_set()

        try:
            if should_stop():
                request_cancellation(queue, job["job_id"], kill_file)
                cancel_and_continue(queue, job["job_id"], "cancelled_before_start")
                continue
            policy_rc = run(["bash", str(ROOT / "worker/policy.sh")], env=env, should_stop=should_stop)
            if lease_loss_requested():
                queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
                continue
            if cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_after_policy")
                continue
            if policy_rc != 0:
                queue.finish(job["job_id"], False, "policy_blocked", args.worker_id, job.get("lease_token"))
                continue

            inspect_rc = run(["bash", str(ROOT / "worker/inspect.sh")], env=env, should_stop=should_stop)
            if lease_loss_requested():
                queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
                continue
            if cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_after_inspection")
                continue
            if inspect_rc != 0:
                queue.finish(job["job_id"], False, "inspection_failed", args.worker_id, job.get("lease_token"))
                continue

            if cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_before_openhands")
                continue

            if job["mode"] == "propose_changes":
                if not os.environ.get("OPENHANDS_AGENT_SERVER_URL") or not os.environ.get("OPENHANDS_SESSION_API_KEY"):
                    queue.finish(job["job_id"], False, "openhands_not_configured", args.worker_id, job.get("lease_token"))
                    continue
                openhands_timeout = args.openhands_timeout_seconds or None
                rc = run(
                    ["bash", str(ROOT / "worker/openhands-run.sh")],
                    env=env,
                    timeout=openhands_timeout,
                    should_stop=should_stop,
                )
                if lease_loss_requested():
                    queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
                    continue
                if rc != 0:
                    latest = queue.get(job["job_id"])
                    if (latest and latest["status"] == "cancel_requested") or kill_file.exists():
                        queue.mark_cancelled(job["job_id"], "cancelled_during_openhands")
                    else:
                        queue.finish(job["job_id"], False, f"openhands_failed:{rc}", args.worker_id, job.get("lease_token"))
                    continue

            if cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_before_tests")
                continue

            test_rc = run(["bash", str(ROOT / "worker/test.sh"), str(repo_dir)], env=env, should_stop=should_stop)
            if lease_loss_requested():
                queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
                continue
            if cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_after_tests")
                continue
            if test_rc != 0:
                queue.finish(job["job_id"], False, "tests_failed", args.worker_id, job.get("lease_token"))
                continue

            if cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_before_completion")
                continue

            completion_env = env | {"OPENHANDS_STATUS": "finished" if job["mode"] == "propose_changes" else "not_requested"}
            completion_rc = run(["bash", str(ROOT / "worker/completion.sh"), str(repo_dir)], env=completion_env, should_stop=should_stop)
            if lease_loss_requested():
                queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
                continue
            if completion_rc != 0:
                queue.finish(job["job_id"], False, "completion_gate_failed", args.worker_id, job.get("lease_token"))
                continue

            if cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_before_finish")
                continue

            if lease_lost.is_set():
                queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
                continue
            queue.finish(job["job_id"], True, worker_id=args.worker_id, lease_token=job.get("lease_token"))
        except subprocess.TimeoutExpired:
            if lease_lost.is_set():
                queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
            elif cancellation_requested(queue, job["job_id"], kill_file):
                if kill_file.exists():
                    queue.cancel(job["job_id"])
                cancel_and_continue(queue, job["job_id"], "cancelled_after_timeout")
            else:
                queue.finish(job["job_id"], False, "worker_timeout", args.worker_id, job.get("lease_token"))
        except Exception as exc:
            if lease_lost.is_set():
                queue.finish(job["job_id"], False, "worker_lease_lost", args.worker_id, job.get("lease_token"))
            else:
                queue.finish(job["job_id"], False, f"worker_exception:{type(exc).__name__}", args.worker_id, job.get("lease_token"))
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2)
            shutil.rmtree(workspace, ignore_errors=True)

        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
