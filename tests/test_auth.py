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


def test_login_is_case_insensitive(client, seed_test_user):
    """5.5.1: email is not case-sensitive — any casing of a registered email
    must authenticate against the lowercase-stored row."""
    base = settings.ADMIN_EMAIL  # stored lowercase
    variants = [base.upper(), base.capitalize(), base.title(), f"  {base.upper()}  "]
    for username in variants:
        response = client.post(
            "/auth/login",
            data={"username": username, "password": settings.ADMIN_PASSWORD},
        )
        assert response.status_code == 200, f"login failed for casing {username!r}"


def test_create_user_normalizes_email_to_lowercase(auth_client):
    """5.5.1: creating a user with mixed-case email stores it lowercase, and
    that user can then log in using any casing."""
    response = auth_client.post(
        "/auth/users",
        json={"email": "MixedCase@Example.com", "password": "case-user-password"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "mixedcase@example.com"

    login = auth_client.post(
        "/auth/login",
        data={"username": "MIXEDCASE@EXAMPLE.COM", "password": "case-user-password"},
    )
    assert login.status_code == 200


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


def test_change_password(auth_client):
    response = auth_client.post(
        "/auth/change-password",
        json={
            "current_password": settings.ADMIN_PASSWORD,
            "new_password": "new-test-password",
        },
    )
    assert response.status_code == 200

    # Old password no longer works
    old_login = auth_client.post(
        "/auth/login",
        data={"username": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert old_login.status_code == 401

    # New password works
    new_login = auth_client.post(
        "/auth/login",
        data={"username": settings.ADMIN_EMAIL, "password": "new-test-password"},
    )
    assert new_login.status_code == 200

    # Restore the original admin password so other tests sharing the
    # session-scoped test DB (seed_test_user / auth_client) keep working —
    # the test DB persists across the whole pytest session (StaticPool).
    restore = auth_client.post(
        "/auth/change-password",
        json={
            "current_password": "new-test-password",
            "new_password": settings.ADMIN_PASSWORD,
        },
    )
    assert restore.status_code == 200


def test_change_password_wrong_current(auth_client):
    response = auth_client.post(
        "/auth/change-password",
        json={
            "current_password": "wrong-current-password",
            "new_password": "new-test-password",
        },
    )
    assert response.status_code == 401


def test_create_user(auth_client):
    response = auth_client.post(
        "/auth/users",
        json={"email": "newuser@example.com", "password": "new-user-password"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@example.com"

    login_response = auth_client.post(
        "/auth/login",
        data={"username": "newuser@example.com", "password": "new-user-password"},
    )
    assert login_response.status_code == 200
