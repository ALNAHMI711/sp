import os
from pathlib import Path

os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-password-that-is-long")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-testing-123456")
os.environ.setdefault("DATABASE_PATH", str(Path(__file__).parent / "test.db"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def login():
    return client.post("/api/login", data={"username": "admin", "password": "test-password-that-is-long"})

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_projects_require_auth():
    client.cookies.clear()
    response = client.get("/api/projects")
    assert response.status_code == 401

def test_create_and_update_project():
    client.cookies.clear()
    assert login().status_code == 200
    response = client.post("/api/projects", json={"name": "اختبار مشروع", "description": "test", "stage": "idea"})
    assert response.status_code == 201
    project_id = response.json()["id"]
    response = client.patch(f"/api/projects/{project_id}/stage", json={"stage": "testing"})
    assert response.status_code == 200
    assert response.json()["stage"] == "testing"
    response = client.get("/api/projects")
    assert any(p["id"] == project_id for p in response.json())
