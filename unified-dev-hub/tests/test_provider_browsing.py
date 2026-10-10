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


def test_github_repository_browsing_uses_read_only_metadata(client, monkeypatch):
    import httpx
    from app import main

    monkeypatch.setenv("GITHUB_READ_TOKEN", "unit-test-token")
    client.cookies.clear()
    assert login(client).status_code == 200

    async def fake_provider_get(url, token, params=None):
        assert url == "https://api.github.com/user/repos"
        assert token == "unit-test-token"
        return httpx.Response(200, json=[{
            "name": "demo", "full_name": "owner/demo",
            "html_url": "https://github.com/owner/demo", "private": True,
            "default_branch": "main", "updated_at": "2026-10-01T00:00:00Z",
            "permissions": {"admin": True}
        }])

    monkeypatch.setattr(main, "provider_get", fake_provider_get)
    response = client.get("/api/github/repos")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["repositories"][0]["full_name"] == "owner/demo"
    assert "permissions" not in response.text
    assert "unit-test-token" not in response.text


def test_vercel_project_browsing_uses_read_only_metadata(client, monkeypatch):
    import httpx
    from app import main

    monkeypatch.setenv("VERCEL_READ_TOKEN", "unit-test-vercel-token")
    client.cookies.clear()
    assert login(client).status_code == 200

    async def fake_provider_get(url, token, params=None):
        assert url == "https://api.vercel.com/v9/projects"
        assert token == "unit-test-vercel-token"
        return httpx.Response(200, json={"projects": [{
            "id": "prj_test", "name": "demo-site",
            "framework": "nextjs", "updatedAt": 1790812800000,
            "env": [{"key": "SECRET", "value": "must-not-be-returned"}]
        }]})

    monkeypatch.setattr(main, "provider_get", fake_provider_get)
    response = client.get("/api/vercel/projects")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["projects"][0]["name"] == "demo-site"
    assert "must-not-be-returned" not in response.text
    assert "unit-test-vercel-token" not in response.text
