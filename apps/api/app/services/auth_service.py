"""Registration, login, and refresh-token issuance/rotation/revocation.
Google OAuth2 code-exchange lives in app/services/google_oauth.py."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.core.time import as_aware, utcnow
from app.models.enums import AuthProvider, CreditReason
from app.models.user import RefreshToken, User
from app.services import credit_service

settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def register_user(db: AsyncSession, *, email: str, password: str, full_name: str | None) -> User:
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
