"""Email verification: the signup-bonus gate that closes the credit-farming
vector (100 free credits for an unverified account, scriptable at will)."""

from __future__ import annotations

from tests.conftest import last_verification_token, register_and_login, unique_email


async def test_unverified_account_has_zero_credits(client):
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": "Test"}
    )
    resp = await client.get("/api/v1/auth/me")
    assert resp.json()["credits_balance"] == 0
    assert resp.json()["email_verified"] is False


async def test_verify_email_grants_signup_bonus_exactly_once(client, db):
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": "Test"}
    )
    token = last_verification_token(email)

    resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert resp.status_code == 200

    me = await client.get("/api/v1/auth/me")
    assert me.json()["credits_balance"] == 100
    assert me.json()["email_verified"] is True

    # the same token cannot be replayed for a second bonus
    resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert resp.status_code == 400

    me = await client.get("/api/v1/auth/me")
    assert me.json()["credits_balance"] == 100


async def test_verify_email_with_invalid_token_is_rejected(client):
    resp = await client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400


async def test_resend_verification_requires_auth(client):
    resp = await client.post("/api/v1/auth/resend-verification")
    assert resp.status_code == 401


async def test_resend_verification_issues_a_working_token(client):
    email = unique_email()
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": "Test"}
    )

    resp = await client.post("/api/v1/auth/resend-verification")
    assert resp.status_code == 200

    token = last_verification_token(email)
    resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert resp.status_code == 200

    me = await client.get("/api/v1/auth/me")
    assert me.json()["credits_balance"] == 100


async def test_resend_verification_rejected_once_already_verified(client):
    await register_and_login(client)  # verify=True by default
    resp = await client.post("/api/v1/auth/resend-verification")
    assert resp.status_code == 400
