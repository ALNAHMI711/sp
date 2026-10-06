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
from app.auth import audit, current_user, login

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


class LoginRequest(BaseModel):
    username: str
    password: str


class JobRequest(BaseModel):
    target_repo: str
    task: str = Field(min_length=1, max_length=8000)
    mode: str = "read_only"
    idempotency_key: str | None = Field(default=None, max_length=200)
    max_attempts: int = Field(default=3, ge=1, le=10)


def queue() -> ControlQueue:
    return ControlQueue(DB)


@app.post("/auth/login")
def auth_login(payload: LoginRequest) -> dict:
    return {"access_token": login(payload.username, payload.password), "token_type": "bearer"}


@app.get("/health")
def health() -> dict:
    queue()
    return {"status": "ok", "kill_switch": KILL_SWITCH.exists()}


@app.post("/jobs")
def create_job(payload: JobRequest, user: dict = Depends(current_user)) -> dict:
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
    audit(user["sub"], "job_created", job_id, payload.target_repo)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(current_user)) -> dict:
    row = queue().get(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return row


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user: dict = Depends(current_user)) -> dict:
    status = queue().cancel(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    audit(user["sub"], "job_cancel_requested", job_id, status)
    return {"job_id": job_id, "status": status}


@app.post("/kill-switch")
def enable_kill_switch(user: dict = Depends(current_user)) -> dict:
    KILL_SWITCH.parent.mkdir(parents=True, exist_ok=True)
    KILL_SWITCH.write_text("enabled\n")
    audit(user["sub"], "kill_switch_enabled")
    return {"enabled": True}


@app.delete("/kill-switch")
def disable_kill_switch(user: dict = Depends(current_user)) -> dict:
    KILL_SWITCH.unlink(missing_ok=True)
    audit(user["sub"], "kill_switch_disabled")
    return {"enabled": False}
