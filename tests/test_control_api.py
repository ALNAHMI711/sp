from pathlib import Path

from fastapi.testclient import TestClient

import app.auth as auth
import app.control_api as api


def configured_client(tmp_path: Path, monkeypatch) -> TestClient:
    db = tmp_path / "control.sqlite3"
    monkeypatch.setattr(api, "DB", str(db))
    monkeypatch.setattr(api, "QUEUE_BACKEND", "sqlite")
    monkeypatch.setattr(api, "POSTGRES_DSN", "")
    monkeypatch.setattr(api, "WORKER_REGISTRY_DB", str(tmp_path / "workers.sqlite3"))
    monkeypatch.setattr(api, "KILL_SWITCH", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(auth, "DB", str(db))
    monkeypatch.setattr(auth, "JWT_SECRET", "test-secret")
    monkeypatch.setenv("CONTROL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("CONTROL_ADMIN_PASSWORD", "strong-test-password")
    return TestClient(api.app, raise_server_exceptions=False)


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "strong-test-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_authentication_and_job_lifecycle(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)

    assert client.get("/jobs/missing").status_code == 401
    headers = login_headers(client)

    created = client.post(
        "/jobs",
        headers=headers,
        json={"target_repo": "ALNAHMI711/sp", "task": "run tests", "mode": "read_only"},
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    fetched = client.get(f"/jobs/{job_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "pending_approval"

    approved = client.post(f"/jobs/{job_id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "queued"

    cancelled = client.post(f"/jobs/{job_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_kill_switch_blocks_new_jobs(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)
    headers = login_headers(client)

    enabled = client.post("/kill-switch", headers=headers)
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True

    blocked = client.post(
        "/jobs",
        headers=headers,
        json={"target_repo": "ALNAHMI711/sp", "task": "run tests", "mode": "read_only"},
    )
    assert blocked.status_code == 423

    disabled = client.delete("/kill-switch", headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


def test_postgres_backend_requires_dsn(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)
    monkeypatch.setattr(api, "QUEUE_BACKEND", "postgres")
    monkeypatch.setattr(api, "POSTGRES_DSN", "")
    assert client.get("/health").status_code == 500

def test_health_checks_queue_connectivity(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)

    class BrokenQueue:
        def ping(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(api, "queue", lambda: BrokenQueue())
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "queue backend unavailable"


import hashlib
import hmac
import json


def github_signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_github_webhook_requires_valid_signature(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)
    monkeypatch.setattr(api, "GITHUB_WEBHOOK_SECRET", "webhook-secret")
    payload = json.dumps({
        "ref": "refs/heads/main",
        "after": "abc123",
        "repository": {"full_name": "ALNAHMI711/sp"},
    }).encode()

    denied = client.post(
        "/webhooks/github",
        content=payload,
        headers={"X-GitHub-Event": "push", "X-GitHub-Delivery": "delivery-1"},
    )
    assert denied.status_code == 403

    accepted = client.post(
        "/webhooks/github",
        content=payload,
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": github_signature(payload, "webhook-secret"),
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "pending_approval"
    job = client.get(f"/jobs/{accepted.json()['job_id']}", headers=login_headers(client))
    assert job.json()["status"] == "pending_approval"


def test_github_webhook_rejects_unapproved_repo_and_deduplicates(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)
    monkeypatch.setattr(api, "GITHUB_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setattr(api, "CONTROL_ALLOWED_REPOS", {"ALNAHMI711/sp"})
    headers_base = {"X-GitHub-Event": "push", "X-GitHub-Delivery": "delivery-2"}

    foreign = json.dumps({"ref": "refs/heads/main", "repository": {"full_name": "someone/else"}}).encode()
    foreign_headers = {**headers_base, "X-Hub-Signature-256": github_signature(foreign, "webhook-secret")}
    assert client.post("/webhooks/github", content=foreign, headers=foreign_headers).status_code == 403

    payload = json.dumps({"ref": "refs/heads/main", "repository": {"full_name": "ALNAHMI711/sp"}}).encode()
    headers = {**headers_base, "X-Hub-Signature-256": github_signature(payload, "webhook-secret")}
    first = client.post("/webhooks/github", content=payload, headers=headers)
    second = client.post("/webhooks/github", content=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_workers_endpoint_reads_sqlite_registry(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)
    registry = api.WorkerRegistry(tmp_path / "workers.sqlite3")
    registry.heartbeat("worker-api", "node-api", "0.1.0")

    response = client.get("/workers", headers=login_headers(client))
    assert response.status_code == 200
    assert response.json()["workers"] == [registry.get("worker-api")]


def test_workers_endpoint_requires_authentication(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)
    assert client.get("/workers").status_code == 401


def test_workers_endpoint_rejects_postgres_without_dsn(tmp_path: Path, monkeypatch) -> None:
    client = configured_client(tmp_path, monkeypatch)
    monkeypatch.setattr(api, "QUEUE_BACKEND", "postgres")
    monkeypatch.setattr(api, "POSTGRES_DSN", "")
    assert client.get("/workers", headers=login_headers(client)).status_code == 503
