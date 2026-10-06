"""Minimal authenticated control API for the autonomous worker.

This is intentionally small: the API can enqueue/inspect/cancel jobs and
operate the kill switch. It never executes repository commands itself.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from worker.control_queue import ControlQueue

app = FastAPI(title="Autonomous Control API", version="0.1.0")
DB = os.getenv("CONTROL_QUEUE_DB", ".data/control-queue.sqlite3")
API_TOKEN = os.getenv("CONTROL_API_TOKEN", "")
KILL_SWITCH = Path(os.getenv("CONTROL_KILL_SWITCH_FILE", ".data/KILL_SWITCH"))


def require_token(request: Request) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="control API token is not configured")
    supplied = request.headers.get("authorization", "")
    expected = f"Bearer {API_TOKEN}"
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


class JobRequest(BaseModel):
    target_repo: str
    task: str = Field(min_length=1, max_length=8000)
    mode: str = "read_only"
    idempotency_key: str | None = Field(default=None, max_length=200)
    max_attempts: int = Field(default=3, ge=1, le=10)


def queue() -> ControlQueue:
    return ControlQueue(DB)


@app.get("/health")
def health() -> dict:
    queue()
    return {"status": "ok", "kill_switch": KILL_SWITCH.exists()}


@app.post("/jobs", dependencies=[Depends(require_token)])
def create_job(payload: JobRequest) -> dict:
    if KILL_SWITCH.exists():
        raise HTTPException(status_code=423, detail="kill switch enabled")
    try:
        job_id = queue().enqueue(
            payload.target_repo, payload.task, payload.mode,
            payload.idempotency_key, payload.max_attempts,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed: jobs.idempotency_key" in str(exc):
            raise HTTPException(status_code=409, detail="duplicate idempotency key") from exc
        raise
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}", dependencies=[Depends(require_token)])
def get_job(job_id: str) -> dict:
    with queue()._db() as db:
        row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return dict(row)


@app.post("/jobs/{job_id}/cancel", dependencies=[Depends(require_token)])
def cancel_job(job_id: str) -> dict:
    queue().cancel(job_id)
    return {"job_id": job_id, "status": "cancel_requested"}


@app.post("/kill-switch", dependencies=[Depends(require_token)])
def enable_kill_switch() -> dict:
    KILL_SWITCH.parent.mkdir(parents=True, exist_ok=True)
    KILL_SWITCH.write_text("enabled\n")
    return {"enabled": True}


@app.delete("/kill-switch", dependencies=[Depends(require_token)])
def disable_kill_switch() -> dict:
    KILL_SWITCH.unlink(missing_ok=True)
    return {"enabled": False}
