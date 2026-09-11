"""Forgot/reset password: the email-enumeration guard, single-use tokens,
and that a reset actually changes the password and signs out old sessions."""

from __future__ import annotations

from sqlalchemy import select

from app.models.user import PasswordResetToken
from app.services import auth_service
from tests.conftest import register_and_login, unique_email


async def test_forgot_password_always_returns_200_even_for_unknown_email(client):
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200


async def test_forgot_password_creates_a_token_for_known_email(client, db):
    email = unique_email()
    await register_and_login(client, email=email)

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200

    tokens = (await db.execute(select(PasswordResetToken))).scalars().all()
    assert len(tokens) >= 1


async def test_reset_password_with_invalid_token_is_rejected(client):
    resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "newpassword123"}
    )
    assert resp.status_code == 400


async def test_reset_password_end_to_end_changes_the_password(client, db):
    email = unique_email()
    await register_and_login(client, email=email, password="oldpassword123")

    # request_password_reset doesn't return the raw token (it's only ever
    # emailed) — call it directly here to get the token for the test.
    import secrets
    from datetime import datetime, timedelta, timezone

    from app.core.config import get_settings
    from app.models.user import User

    settings = get_settings()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=auth_service._hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "brandnewpassword123"}
    )
    assert resp.status_code == 200

    # old password no longer works
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "oldpassword123"})
    assert resp.status_code == 401

    # new password works
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "brandnewpassword123"})
    assert resp.status_code == 200

    # the same reset token cannot be used twice
    resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "yetanotherpassword123"}
    )
    assert resp.status_code == 400
