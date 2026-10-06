"""Minimal authenticated control API for the autonomous worker.

This is intentionally small: the API can enqueue/inspect/cancel jobs and
operate the kill switch. It never executes repository commands itself.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from worker.control_queue import ControlQueue
from worker.postgres_queue import PostgresQueue
from app.auth import audit, current_user, login, require_scope

app = FastAPI(title="Autonomous Control API", version="0.1.0")
DB = os.getenv("CONTROL_QUEUE_DB", ".data/control-queue.sqlite3")
QUEUE_BACKEND = os.getenv("CONTROL_QUEUE_BACKEND", "sqlite").strip().lower()
POSTGRES_DSN = os.getenv("CONTROL_POSTGRES_DSN", "").strip()

def queue():
    if QUEUE_BACKEND == "sqlite":
        return ControlQueue(DB)
    if QUEUE_BACKEND == "postgres":
        if not POSTGRES_DSN:
            raise RuntimeError("CONTROL_POSTGRES_DSN is required for postgres backend")
        return PostgresQueue(POSTGRES_DSN)
    raise RuntimeError("unsupported CONTROL_QUEUE_BACKEND")
KILL_SWITCH = Path(os.getenv("CONTROL_KILL_SWITCH_FILE", ".data/KILL_SWITCH"))
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
CONTROL_ALLOWED_REPOS = {item.strip() for item in os.getenv("CONTROL_ALLOWED_REPOS", "ALNAHMI711/sp").split(",") if item.strip()}


class LoginRequest(BaseModel):
    username: str
    password: str


def _verify_github_signature(body: bytes, signature: str | None) -> bool:
    if not GITHUB_WEBHOOK_SECRET or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class JobRequest(BaseModel):
    target_repo: str
    task: str = Field(min_length=1, max_length=8000)
    mode: str = "read_only"
    idempotency_key: str | None = Field(default=None, max_length=200)
    max_attempts: int = Field(default=3, ge=1, le=10)




@app.post("/webhooks/github")
async def github_webhook(request: Request) -> dict:
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    delivery_id = request.headers.get("x-github-delivery", "").strip()
    event = request.headers.get("x-github-event", "").strip().lower()
    if not GITHUB_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="GitHub webhook secret is not configured")
    if not _verify_github_signature(body, signature):
        raise HTTPException(status_code=403, detail="invalid webhook signature")
    if not delivery_id:
        raise HTTPException(status_code=400, detail="missing GitHub delivery id")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc

    if event == "ping":
        return {"accepted": True, "event": "ping"}
    if event != "push":
        return {"accepted": True, "event": event, "status": "ignored"}

    repository = payload.get("repository") or {}
    target_repo = str(repository.get("full_name") or "").strip()
    if not target_repo:
        raise HTTPException(status_code=400, detail="repository.full_name is required")
    if target_repo not in CONTROL_ALLOWED_REPOS:
        raise HTTPException(status_code=403, detail="repository is not approved")
    ref = str(payload.get("ref") or "").strip()
    after = str(payload.get("after") or "").strip()
    task = f"Inspect GitHub push for {target_repo}"
    if ref:
        task += f" on {ref}"
    if after:
        task += f" at {after[:40]}"
    try:
        job_id = queue().enqueue(
            target_repo, task, "read_only", idempotency_key=f"github:{delivery_id}"
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed: jobs.idempotency_key" in str(exc) or "duplicate key" in str(exc).lower():
            return {"accepted": True, "event": event, "status": "duplicate", "delivery_id": delivery_id}
        raise
    audit("github-webhook", "webhook_job_created", job_id, f"{event}:{delivery_id}")
    return {"accepted": True, "event": event, "status": "pending_approval", "job_id": job_id, "delivery_id": delivery_id}


@app.post("/auth/login")
def auth_login(payload: LoginRequest) -> dict:
    return {"access_token": login(payload.username, payload.password), "token_type": "bearer"}


@app.get("/health")
def health() -> dict:
    queue()
    return {"status": "ok", "kill_switch": KILL_SWITCH.exists()}


@app.post("/jobs")
def create_job(payload: JobRequest, user: dict = Depends(current_user)) -> dict:
    require_scope(user, "jobs:write")
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
    return {"job_id": job_id, "status": "pending_approval"}


@app.post("/jobs/{job_id}/approve")
def approve_job(job_id: str, user: dict = Depends(current_user)) -> dict:
    require_scope(user, "jobs:approve")
    approved = queue().approve(job_id)
    if not approved:
        row = queue().get(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        raise HTTPException(status_code=409, detail="job is not pending approval")
    audit(user["sub"], "job_approved", job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(current_user)) -> dict:
    require_scope(user, "jobs:read")
    row = queue().get(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return row


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user: dict = Depends(current_user)) -> dict:
    require_scope(user, "jobs:cancel")
    status = queue().cancel(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    audit(user["sub"], "job_cancel_requested", job_id, status)
    return {"job_id": job_id, "status": status}


@app.post("/kill-switch")
def enable_kill_switch(user: dict = Depends(current_user)) -> dict:
    require_scope(user, "kill:write")
    KILL_SWITCH.parent.mkdir(parents=True, exist_ok=True)
    KILL_SWITCH.write_text("enabled\n")
    result = queue().request_kill_switch()
    audit(user["sub"], "kill_switch_enabled", detail=str(result))
    return {"enabled": True, **result}


@app.delete("/kill-switch")
def disable_kill_switch(user: dict = Depends(current_user)) -> dict:
    require_scope(user, "kill:write")
    KILL_SWITCH.unlink(missing_ok=True)
    audit(user["sub"], "kill_switch_disabled")
    return {"enabled": False}
