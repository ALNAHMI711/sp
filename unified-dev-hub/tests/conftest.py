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
