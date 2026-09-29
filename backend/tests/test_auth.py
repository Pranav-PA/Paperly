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
