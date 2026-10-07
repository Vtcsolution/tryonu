"""Admitad (Mitgo) affiliate network API: authentication and read-only calls.

Admitad's API uses OAuth2 client credentials: POST /token/ with Basic auth
(base64 of "client_id:client_secret") returns a bearer token limited to the
scopes asked for. Nothing here writes to the Admitad account; this module
only gets a token and reads (the account, its ad spaces).

Credentials come from settings (ADMITAD_CLIENT_ID / ADMITAD_CLIENT_SECRET /
ADMITAD_BASE64_HEADER, read from the .env names client_id / client_secret /
base64_header). Nothing in this module logs or returns a credential or token.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


class AdmitadError(Exception):
    """An Admitad request failed. The message never contains a credential."""


@dataclass(frozen=True)
class AdmitadToken:
    access_token: str
    scopes: list[str]
    expires_in: int

    def __repr__(self) -> str:  # never show the token itself
        return f"AdmitadToken(scopes={self.scopes}, expires_in={self.expires_in})"


def configuration() -> dict:
    """What is set, as booleans and checks only: safe to print."""
    s = get_settings()
    client_id, secret, header = s.ADMITAD_CLIENT_ID, s.ADMITAD_CLIENT_SECRET, s.ADMITAD_BASE64_HEADER
    header_matches: bool | None = None
    if client_id and secret and header:
        try:
            header_matches = base64.b64decode(header.strip(), validate=True).decode() == f"{client_id}:{secret}"
        except (binascii.Error, UnicodeDecodeError):
            header_matches = False
    return {
        "client_id_loaded": bool(client_id),
        "client_secret_loaded": bool(secret),
        "base64_header_loaded": bool(header),
        "base64_header_matches_id_and_secret": header_matches,
    }


def _basic_header() -> str:
    """The Basic auth value: the configured header, or one built from the
    id and secret when only those are set."""
    s = get_settings()
    if s.ADMITAD_BASE64_HEADER:
        return s.ADMITAD_BASE64_HEADER.strip()
    if s.ADMITAD_CLIENT_ID and s.ADMITAD_CLIENT_SECRET:
        return base64.b64encode(f"{s.ADMITAD_CLIENT_ID}:{s.ADMITAD_CLIENT_SECRET}".encode()).decode()
    raise AdmitadError("Admitad is not configured: set client_id and client_secret (or base64_header)")


async def get_token(scopes: list[str], *, client: httpx.AsyncClient | None = None) -> AdmitadToken:
    """A client-credentials token for these scopes."""
    s = get_settings()
    if not s.ADMITAD_CLIENT_ID:
        raise AdmitadError("Admitad is not configured: client_id is missing")
    own = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        resp = await client.post(
            f"{s.ADMITAD_API_BASE_URL}/token/",
            headers={"Authorization": f"Basic {_basic_header()}"},
            data={"grant_type": "client_credentials", "client_id": s.ADMITAD_CLIENT_ID, "scope": " ".join(scopes)},
        )
    except httpx.RequestError as exc:
        raise AdmitadError(f"Admitad token request could not be sent: {type(exc).__name__}") from exc
    finally:
        if own:
            await client.aclose()
    if resp.status_code != 200:
        raise AdmitadError(f"Admitad token request failed: HTTP {resp.status_code} {_error_text(resp)}")
    body = resp.json()
    if not body.get("access_token"):
        raise AdmitadError("Admitad token response had no access token")
    return AdmitadToken(
        access_token=body["access_token"],
        scopes=str(body.get("scope") or "").split(),
        expires_in=int(body.get("expires_in") or 0),
    )


async def get_json(token: AdmitadToken, path: str, params: dict | None = None) -> dict | list:
    """One read-only GET against the Admitad API."""
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{s.ADMITAD_API_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {token.access_token}"},
                params=params,
            )
    except httpx.RequestError as exc:
        raise AdmitadError(f"Admitad request {path} could not be sent: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        raise AdmitadError(f"Admitad request {path} failed: HTTP {resp.status_code} {_error_text(resp)}")
    return resp.json()


def _error_text(resp: httpx.Response) -> str:
    """Admitad's own error code and description, never the request."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    if isinstance(body, dict):
        return " ".join(str(body.get(k)) for k in ("error", "error_description", "detail") if body.get(k))[:200]
    return str(body)[:200]
