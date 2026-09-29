def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "testteacher", "password": "testpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "testteacher", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_nonexistent_user(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "unknownuser", "password": "anypassword"}
    )
    assert response.status_code == 401


def test_get_current_user_me(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testteacher"
    assert data["role"] == "teacher"
    assert data["is_active"] is True


def test_get_me_unauthorized(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_password_hash_roundtrip():
    from app.core.security import get_password_hash, verify_password
    h = get_password_hash("Maple-1234-River")
    assert h.startswith("scrypt$")
    assert verify_password("Maple-1234-River", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "not-a-valid-hash")


def test_change_password(client, auth_headers):
    bad = client.post("/api/v1/auth/change-password",
                      json={"current_password": "nope", "new_password": "newpassword123"}, headers=auth_headers)
    assert bad.status_code == 400
    ok = client.post("/api/v1/auth/change-password",
                     json={"current_password": "testpassword123", "new_password": "newpassword123"}, headers=auth_headers)
    assert ok.status_code == 204
    assert client.post("/api/v1/auth/login/json", json={"username": "testteacher", "password": "newpassword123"}).status_code == 200
    # restore for other tests
    client.post("/api/v1/auth/change-password",
                json={"current_password": "newpassword123", "new_password": "testpassword123"}, headers=auth_headers)


def test_health_reports_demo_mode(client):
    data = client.get("/health").json()
    assert data["status"] == "healthy"
    assert data["ai_mode"] == "demo"
