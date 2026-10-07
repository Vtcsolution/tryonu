"""Admitad client: configuration checks and the token request. Offline: httpx is mocked."""

from __future__ import annotations

import base64

import httpx
import pytest

from app.core.config import get_settings
from app.services import admitad

_ID, _SECRET = "id-not-real-000000000000000000", "secret-not-real-0000000000000"


@pytest.fixture
def creds(monkeypatch):  # noqa: ANN001, ANN201
    s = get_settings()
    monkeypatch.setattr(s, "ADMITAD_CLIENT_ID", _ID)
    monkeypatch.setattr(s, "ADMITAD_CLIENT_SECRET", _SECRET)
    monkeypatch.setattr(s, "ADMITAD_BASE64_HEADER", base64.b64encode(f"{_ID}:{_SECRET}".encode()).decode())
    return s


def test_configuration_reports_what_is_loaded_and_never_the_values(creds):  # noqa: ANN001
    config = admitad.configuration()
    assert config == {
        "client_id_loaded": True,
        "client_secret_loaded": True,
        "base64_header_loaded": True,
        "base64_header_matches_id_and_secret": True,
    }
    assert _ID not in str(config) and _SECRET not in str(config)


def test_a_header_for_other_credentials_is_flagged(creds, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(creds, "ADMITAD_BASE64_HEADER", base64.b64encode(b"other:pair").decode())
    assert admitad.configuration()["base64_header_matches_id_and_secret"] is False


async def test_the_token_request_is_client_credentials_with_basic_auth(creds):  # noqa: ANN001
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "tok", "scope": "websites", "expires_in": 604800})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        token = await admitad.get_token(["websites"], client=client)

    assert seen["url"] == "https://api.admitad.com/token/"
    assert seen["auth"] == "Basic " + creds.ADMITAD_BASE64_HEADER
    assert "grant_type=client_credentials" in seen["body"] and "scope=websites" in seen["body"]
    assert token.scopes == ["websites"] and "tok" not in repr(token)


async def test_a_refused_token_request_says_why_without_the_credentials(creds):  # noqa: ANN001
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_client", "error_description": "bad client"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(admitad.AdmitadError) as caught:
            await admitad.get_token(["websites"], client=client)
    message = str(caught.value)
    assert "invalid_client" in message and _ID not in message and _SECRET not in message
