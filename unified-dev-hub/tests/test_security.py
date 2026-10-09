def test_dashboard_serves_arabic_html_with_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "مركز التطوير الموحد" in response.text
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in response.headers.get("content-security-policy", "")

def test_cross_origin_mutation_is_blocked(client):
    response = client.post(
        "/api/login",
        data={"username": "admin", "password": "test-password-that-is-long"},
        headers={"origin": "https://attacker.example", "host": "localhost:8000", "x-forwarded-proto": "http"},
    )
    assert response.status_code == 403

def test_health_does_not_require_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
