"""Google OAuth2 authorization-code exchange (no SDK — three plain HTTP
calls). Requires GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI
(see .env.example); endpoints return 501 until those are set."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REDIRECT_URI)


def _require_configured() -> None:
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google login is not configured on this server (GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI unset)",
        )


def build_authorize_url(state: str | None = None) -> str:
    _require_configured()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": state or secrets.token_urlsafe(16),
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    sub: str
    email: str
    name: str | None
    picture: str | None


async def exchange_code_for_profile(code: str) -> GoogleProfile:
    _require_configured()

    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google code exchange failed")
        access_token = token_resp.json()["access_token"]

        userinfo_resp = await client.get(
            _USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_resp.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not fetch Google profile")
        data = userinfo_resp.json()

    return GoogleProfile(sub=data["sub"], email=data["email"], name=data.get("name"), picture=data.get("picture"))
