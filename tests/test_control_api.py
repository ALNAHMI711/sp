from pathlib import Path

from fastapi.testclient import TestClient

import app.auth as auth
import app.control_api as api


def configured_client(tmp_path: Path, monkeypatch) -> TestClient:
    db = tmp_path / "control.sqlite3"
    monkeypatch.setattr(api, "DB", str(db))
    monkeypatch.setattr(api, "QUEUE_BACKEND", "sqlite")
    monkeypatch.setattr(api, "POSTGRES_DSN", "")
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
    assert fetched.json()["status"] == "queued"

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
