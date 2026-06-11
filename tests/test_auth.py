from app.config import settings


def test_login_success(client, seed_test_user):
    response = client.post(
        "/auth/login",
        data={"username": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    cookie = response.cookies.get("access_token")
    assert cookie is not None

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "httponly" in set_cookie_header.lower()


def test_login_invalid_credentials(client, seed_test_user):
    response = client.post(
        "/auth/login",
        data={"username": settings.ADMIN_EMAIL, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_protected_requires_auth(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_protected_rejects_invalid_token(client):
    client.cookies.set("access_token", "this-is-not-a-valid-jwt")
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_logout_clears_session(auth_client):
    response = auth_client.get("/auth/me")
    assert response.status_code == 200

    logout_response = auth_client.post("/auth/logout")
    assert logout_response.status_code == 200

    follow_up = auth_client.get("/auth/me")
    assert follow_up.status_code == 401
