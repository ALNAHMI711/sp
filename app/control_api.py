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
from worker.worker_registry import WorkerRegistry
from worker.postgres_worker_registry import PostgresWorkerRegistry
from worker.repo_policy import approved_repositories
from app.auth import audit, current_user, login, require_scope
from app.secrets_store import ALLOWED_SECRETS, delete_secret, get_secret, secret_status, set_secret

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
WORKER_REGISTRY_DB = os.getenv("CONTROL_WORKER_REGISTRY_DB", str(Path(DB).with_name("workers.sqlite3")))
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
CONTROL_ALLOWED_REPOS = approved_repositories()


class LoginRequest(BaseModel):
    username: str
    password: str


def _verify_github_signature(body: bytes, signature: str | None, secret: str | None = None) -> bool:
    active_secret = secret if secret is not None else (get_secret("GITHUB_WEBHOOK_SECRET") or GITHUB_WEBHOOK_SECRET)
    if not active_secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        active_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class JobRequest(BaseModel):
    target_repo: str
    task: str = Field(min_length=1, max_length=8000)
    mode: str = "read_only"
    idempotency_key: str | None = Field(default=None, max_length=200)
    max_attempts: int = Field(default=3, ge=1, le=10)


class IntegrationSecretsRequest(BaseModel):
    secrets: dict[str, str] = Field(default_factory=dict)




@app.post("/webhooks/github")
async def github_webhook(request: Request) -> dict:
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    delivery_id = request.headers.get("x-github-delivery", "").strip()
    event = request.headers.get("x-github-event", "").strip().lower()
    webhook_secret = get_secret("GITHUB_WEBHOOK_SECRET") or GITHUB_WEBHOOK_SECRET
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="GitHub webhook secret is not configured")
    if not _verify_github_signature(body, signature, webhook_secret):
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


@app.get("/settings/integrations")
def get_integration_settings(user: dict = Depends(current_user)) -> dict:
    require_scope(user, "secrets:read")
    return {
        "configured": secret_status(),
        "storage": "encrypted-control-panel",
        "catalog": [
            {"name": "GITHUB_WEBHOOK_SECRET", "label": "GitHub Webhook Secret", "required": False, "purpose": "التحقق من توقيع Webhook؛ مطلوب فقط عند تفعيل استقبال أحداث GitHub."},
            {"name": "GITHUB_APP_ID", "label": "GitHub App ID", "required": False, "purpose": "معرّف تطبيق GitHub؛ لا يكفي وحده لتفعيل اتصال التطبيق."},
            {"name": "GITHUB_APP_INSTALLATION_ID", "label": "GitHub App Installation ID", "required": False, "purpose": "معرّف تثبيت GitHub App؛ يستخدم عند استكمال تكامل التطبيق."},
            {"name": "GITHUB_APP_PRIVATE_KEY", "label": "GitHub App Private Key", "required": False, "purpose": "المفتاح الخاص لتوقيع JWT الخاص بالتطبيق؛ لا ترفعه إلى GitHub."},
            {"name": "TELEGRAM_BOT_TOKEN", "label": "Telegram Bot Token", "required": False, "purpose": "يلزم فقط عند تفعيل بوت Telegram."},
            {"name": "TELEGRAM_ALLOWED_USER_IDS", "label": "Telegram Allowed User IDs", "required": False, "purpose": "قائمة معرّفات المستخدمين المصرّح لهم بالتحكم عبر Telegram."},
            {"name": "OPENAI_API_KEY", "label": "OpenAI API Key", "required": False, "purpose": "يلزم فقط عند تفعيل ميزات OpenAI؛ لا تُفعّل الميزة بمجرد حفظ المفتاح."},
            {"name": "AI_API_KEY", "label": "AI API Key (عام)", "required": False, "purpose": "مفتاح مزوّد ذكاء اصطناعي آخر عند إضافة موصل يدعمه."},
        ],
        "deployment_note": "مفاتيح التشفير والمصادقة والاتصال بقاعدة البيانات تظل إعدادات نشر آمنة؛ لا تُحفظ داخل إعدادات التكامل.",
    }


@app.put("/settings/integrations")
def update_integration_settings(
    payload: IntegrationSecretsRequest, user: dict = Depends(current_user)
) -> dict:
    require_scope(user, "secrets:write")
    unknown = set(payload.secrets) - ALLOWED_SECRETS
    if unknown:
        raise HTTPException(status_code=400, detail="unsupported integration setting")
    saved = []
    for name, value in payload.secrets.items():
        if value.strip():
            set_secret(name, value)
            saved.append(name)
    if saved:
        audit(user["sub"], "integration_secrets_updated", ",".join(sorted(saved)))
    return {"saved": sorted(saved), "configured": secret_status()}


@app.delete("/settings/integrations/{name}")
def remove_integration_setting(name: str, user: dict = Depends(current_user)) -> dict:
    require_scope(user, "secrets:write")
    if name not in ALLOWED_SECRETS:
        raise HTTPException(status_code=404, detail="integration setting not found")
    removed = delete_secret(name)
    audit(user["sub"], "integration_secret_deleted", name)
    return {"deleted": removed, "configured": secret_status()}


@app.get("/health")
def health() -> dict:
    try:
        queue().ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="queue backend unavailable") from exc
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


@app.get("/workers")
def list_workers(user: dict = Depends(current_user)) -> dict:
    require_scope(user, "jobs:read")
    if QUEUE_BACKEND == "postgres":
        if not POSTGRES_DSN:
            raise HTTPException(status_code=503, detail="CONTROL_POSTGRES_DSN is required")
        registry = PostgresWorkerRegistry(POSTGRES_DSN)
    else:
        registry = WorkerRegistry(WORKER_REGISTRY_DB)
    return {"workers": registry.list()}


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
