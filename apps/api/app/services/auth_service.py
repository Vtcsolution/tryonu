"""Registration, login, refresh-token issuance/rotation/revocation, and
password reset. Google OAuth2 code-exchange lives in
app/services/google_oauth.py."""

from __future__ import annotations

import hashlib
import secrets
from urllib.parse import quote
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.core.time import as_aware, utcnow
from app.email.registry import get_email_provider
from app.models.enums import AuthProvider, CreditReason
from app.models.user import EmailVerificationToken, PasswordResetToken, RefreshToken, User
from app.services import credit_service

settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def register_user(
    db: AsyncSession, *, email: str, password: str, full_name: str | None, next_path: str | None = None
) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        auth_provider=AuthProvider.LOCAL,
    )
    db.add(user)
    await db.flush()
    if settings.SIGNUP_FREE_CREDITS > 0:  # 0: new users start at 0 and buy a plan
        await credit_service.grant(
            db,
            user_id=user.id,
            amount=settings.SIGNUP_FREE_CREDITS,
            reason=CreditReason.SIGNUP_BONUS,
            reference_type="user",
            reference_id=user.id,
            note="Welcome bonus",
        )
    await _send_verification_email(db, user, next_path)
    await db.commit()
    await db.refresh(user)
    return user


async def _send_verification_email(db: AsyncSession, user: User, next_path: str | None = None) -> None:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES),
        )
    )
    from app.email.templates import action_email, site_url

    # (FRONTEND_URL can end in "/": live, the link came out as tryonu.app//verify-email)
    verify_url = site_url(f"/verify-email?token={raw_token}")
    # a look someone shared with them: the email leads back to it (on any phone or computer)
    if next_path and next_path.startswith("/") and not next_path.startswith("//") and "\\" not in next_path:
        verify_url += f"&next={quote(next_path[:300], safe='')}"
    text, page = action_email(
        "Welcome to TryOnU!",
        [
            "Please confirm your email address, so we can send you your looks and keep your account safe.",
            f"The button works for {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES // 60} hours.",
        ],
        "Confirm my email",
        verify_url,
        after=["If you didn't create a TryOnU account, you can ignore this email."],
    )
    try:
        await get_email_provider().send(to=user.email, subject="Confirm your TryOnU email", text_body=text, html_body=page)
    except Exception as exc:  # noqa: BLE001 - signing up works even when email is down; they can ask again
        logger.warning("verification_email_failed", user_id=user.id, error=str(exc)[:200])


async def verify_email(db: AsyncSession, *, token: str) -> User:
    token_hash = _hash_token(token)
    result = await db.execute(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()

    if stored is None or stored.used_at is not None or as_aware(stored.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link is invalid or expired")

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link is invalid or expired")

    stored.used_at = datetime.now(timezone.utc)
    user.email_verified = True
    await db.commit()
    await db.refresh(user)
    logger.info("email_verified", user_id=user.id)
    return user


async def resend_verification_email(db: AsyncSession, *, user: User) -> None:
    if user.email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already verified")
    await _send_verification_email(db, user)
    await db.commit()
    logger.info("verification_email_resent", user_id=user.id)


async def authenticate_local(db: AsyncSession, *, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def find_or_create_google_user(
    db: AsyncSession, *, google_sub: str, email: str, full_name: str | None, avatar_url: str | None
) -> User:
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()
    if user is not None:
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    # link by email if a local account already exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        user.google_sub = google_sub
        user.auth_provider = AuthProvider.GOOGLE
        user.avatar_url = user.avatar_url or avatar_url
        user.email_verified = True
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    user = User(
        email=email,
        full_name=full_name,
        avatar_url=avatar_url,
        auth_provider=AuthProvider.GOOGLE,
        google_sub=google_sub,
        email_verified=True,
    )
    db.add(user)
    await db.flush()
    if settings.SIGNUP_FREE_CREDITS > 0:  # 0: new users start at 0 and buy a plan
        await credit_service.grant(
            db,
            user_id=user.id,
            amount=settings.SIGNUP_FREE_CREDITS,
            reason=CreditReason.SIGNUP_BONUS,
            reference_type="user",
            reference_id=user.id,
            note="Welcome bonus",
        )
    await db.commit()
    await db.refresh(user)
    return user


async def issue_tokens(db: AsyncSession, user: User, *, user_agent: str | None = None) -> tuple[str, str]:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent[:512] if user_agent else None,
        )
    )
    await db.commit()
    return access_token, refresh_token


async def rotate_refresh_token(db: AsyncSession, *, refresh_token: str, user_id: str) -> tuple[str, str]:
    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user_id,
        )
    )
    stored = result.scalar_one_or_none()
    if stored is None or stored.revoked_at is not None or as_aware(stored.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired")

    stored.revoked_at = datetime.now(timezone.utc)
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or disabled")

    return await issue_tokens(db, user)


async def revoke_refresh_token(db: AsyncSession, *, refresh_token: str, user_id: str) -> None:
    token_hash = _hash_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.user_id == user_id)
    )
    stored = result.scalar_one_or_none()
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        await db.commit()


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    )
    now = datetime.now(timezone.utc)
    for token in result.scalars().all():
        token.revoked_at = now


async def request_password_reset(db: AsyncSession, *, email: str) -> None:
    """Always succeeds from the caller's point of view — whether or not
    the email is registered is never revealed (prevents account
    enumeration). If it *is* registered, emails a single-use reset link
    valid for PASSWORD_RESET_TOKEN_EXPIRE_MINUTES."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        logger.info("password_reset_requested_unknown_email")
        return

    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    await db.commit()

    from app.email.templates import action_email, site_url

    reset_url = site_url(f"/reset-password?token={raw_token}")
    text, page = action_email(
        "Reset your password",
        [
            "Someone asked to reset the password of your TryOnU account. Choose a new one with the button below.",
            f"The button works for {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.",
        ],
        "Choose a new password",
        reset_url,
        after=["If you didn't ask for this, ignore this email: your password stays the same."],
    )
    try:
        await get_email_provider().send(to=user.email, subject="Reset your TryOnU password", text_body=text, html_body=page)
    except Exception as exc:  # noqa: BLE001 - the answer to the visitor is the same either way
        logger.warning("password_reset_email_failed", user_id=user.id, error=str(exc)[:200])
        return
    logger.info("password_reset_email_sent", user_id=user.id)


async def change_password(db: AsyncSession, *, user: User, current_password: str | None, new_password: str) -> None:
    """A signed-in user changes their password. The current one must match,
    unless the account has none yet (Google sign-up), which sets its first.
    Every other device is signed out; the caller issues this session new tokens."""
    if user.hashed_password and not (current_password and verify_password(current_password, user.hashed_password)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your current password is not correct")
    if user.hashed_password and verify_password(new_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The new password must be different")
    user.hashed_password = hash_password(new_password)
    await revoke_all_refresh_tokens(db, user.id)
    await db.commit()
    logger.info("password_changed", user_id=user.id)


async def reset_password(db: AsyncSession, *, token: str, new_password: str) -> None:
    token_hash = _hash_token(token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()

    if (
        stored is None
        or stored.used_at is not None
        or as_aware(stored.expires_at) < utcnow()
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or expired")

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or expired")

    user.hashed_password = hash_password(new_password)
    stored.used_at = datetime.now(timezone.utc)
    # a password reset is a strong signal to sign the account out everywhere
    await revoke_all_refresh_tokens(db, user.id)
    await db.commit()
    logger.info("password_reset_completed", user_id=user.id)
