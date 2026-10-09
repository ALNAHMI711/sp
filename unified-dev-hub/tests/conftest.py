import os
from pathlib import Path

os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-password-that-is-long")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-testing-123456")
os.environ.setdefault("DATABASE_PATH", str(Path(__file__).parent / "test.db"))

import pytest
from fastapi.testclient import TestClient
from app.main import app, startup

@pytest.fixture(autouse=True)
def initialize_database():
    startup()
    yield

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
