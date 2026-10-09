def login(client):
    return client.post("/api/login", data={"username": "admin", "password": "test-password-that-is-long"})

def test_github_repository_list_requires_auth(client):
    client.cookies.clear()
    assert client.get("/api/github/repos").status_code == 401

def test_provider_browsing_requires_configured_token(client, monkeypatch):
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_READ_TOKEN", raising=False)
    client.cookies.clear()
    assert login(client).status_code == 200
    assert client.get("/api/github/repos").status_code == 503
    assert client.get("/api/vercel/projects").status_code == 503
