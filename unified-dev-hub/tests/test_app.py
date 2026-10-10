import os

os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-password-that-is-long")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-testing-123456")

from fastapi.testclient import TestClient
import pytest
from app import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "projects.db")
    with TestClient(main.app) as test_client:
        yield test_client


def login(client):
    return client.post(
        "/api/login",
        data={"username": "admin", "password": "test-password-that-is-long"},
    )


def create_project(client, name="مشروع اختبار", **overrides):
    payload = {"name": name, "description": "وصف للاختبار", "stage": "idea"}
    payload.update(overrides)
    return client.post("/api/projects", json=payload)


def test_health_and_security_headers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_home_page_is_arabic_rtl(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'lang="ar"' in response.text
    assert 'dir="rtl"' in response.text


def test_projects_require_authentication(client):
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/audit").status_code == 401


def test_login_rejects_wrong_credentials(client):
    response = client.post(
        "/api/login",
        data={"username": "admin", "password": "incorrect-password"},
    )
    assert response.status_code == 401
    assert "udh_session" not in response.cookies


def test_login_session_and_logout(client):
    response = login(client)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "udh_session" in client.cookies
    assert client.get("/api/session").json()["authenticated"] is True
    assert client.post("/api/logout").status_code == 200
    client.cookies.clear()
    assert client.get("/api/session").json()["authenticated"] is False


def test_create_update_audit_and_delete_project(client):
    assert login(client).status_code == 200
    response = create_project(client)
    assert response.status_code == 201
    project_id = response.json()["id"]
    assert response.json()["stage"] == "idea"

    response = client.patch(
        f"/api/projects/{project_id}/stage", json={"stage": "testing"}
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "testing"

    audit = client.get("/api/audit")
    assert audit.status_code == 200
    actions = [event["action"] for event in audit.json()]
    assert "project_created" in actions
    assert "stage_updated" in actions

    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get("/api/projects").json() == []
    assert client.delete(f"/api/projects/{project_id}").status_code == 404


def test_invalid_stage_is_rejected_on_update(client):
    assert login(client).status_code == 200
    response = client.patch(
        "/api/projects/1/stage", json={"stage": "launch-everything"}
    )
    assert response.status_code == 422


def test_repo_url_must_be_https(client):
    assert login(client).status_code == 200
    response = create_project(client, repo_url="http://example.com/repo")
    assert response.status_code == 422


def test_integration_status_does_not_expose_tokens(client, monkeypatch):
    assert login(client).status_code == 200
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_READ_TOKEN", raising=False)
    response = client.get("/api/integrations")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "read_only"
    assert len(payload["integrations"]) == 2
    assert all(item["status"] == "missing_token" for item in payload["integrations"])
    assert "CHANGE_ME" not in response.text


def test_provider_endpoints_report_missing_tokens(client, monkeypatch):
    assert login(client).status_code == 200
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_READ_TOKEN", raising=False)
    assert client.get("/api/github/repos").status_code == 503
    assert client.get("/api/vercel/projects").status_code == 503


def test_cross_origin_mutation_is_blocked(client):
    response = client.post(
        "/api/login",
        data={"username": "admin", "password": "test-password-that-is-long"},
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403
