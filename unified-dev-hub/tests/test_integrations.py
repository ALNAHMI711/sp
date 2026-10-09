def login(client):
    return client.post("/api/login", data={"username": "admin", "password": "test-password-that-is-long"})

def test_integrations_require_auth(client):
    client.cookies.clear()
    response = client.get("/api/integrations")
    assert response.status_code == 401

def test_integrations_hide_tokens_and_report_missing(client, monkeypatch):
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_READ_TOKEN", raising=False)
    client.cookies.clear()
    assert login(client).status_code == 200
    response = client.get("/api/integrations")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "read_only"
    assert all(item["status"] == "missing_token" for item in payload["integrations"])
    assert all("token" not in item for item in payload["integrations"])

def test_repo_url_requires_https(client):
    client.cookies.clear()
    assert login(client).status_code == 200
    response = client.post("/api/projects", json={"name": "Bad URL", "repo_url": "javascript:alert(1)"})
    assert response.status_code == 422
