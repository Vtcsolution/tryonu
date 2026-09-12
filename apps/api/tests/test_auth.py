"""Register/login/session/authorization — no mocked HTTP needed, this is
all real app + real (test) DB."""

from __future__ import annotations

from tests.conftest import register_and_login, unique_email


async def test_register_withholds_signup_bonus_until_verified(client):
    """Credits are only granted on email verification (see
    test_email_verification.py) — this prevents scripting unlimited free
    accounts for free AI usage."""
    email = unique_email()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["credits_balance"] == 0
    assert data["user"]["email_verified"] is False
    assert data["user"]["is_admin"] is False
    assert "access_token" in data


async def test_register_and_login_helper_grants_signup_bonus_once_verified(client):
    data = await register_and_login(client)
    assert data["user"]["credits_balance"] == 100
    assert data["user"]["email_verified"] is True


async def test_duplicate_email_is_rejected(client):
    email = unique_email()
    await register_and_login(client, email=email)

    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 409


async def test_login_wrong_password_is_401(client):
    email = unique_email()
    await register_and_login(client, email=email)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "totally-wrong"},
    )
    assert resp.status_code == 401


async def test_me_requires_authentication(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user_when_authenticated(client):
    data = await register_and_login(client)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == data["user"]["email"]


async def test_logout_clears_session(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_google_login_501_when_not_configured(client):
    # No GOOGLE_CLIENT_ID/SECRET set in the test environment — must fail
    # clearly rather than pretend to work.
    resp = await client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert resp.status_code == 501
