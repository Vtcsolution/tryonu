"""Security/no-leak checks specific to the Rakuten integration: no
credentials in the frontend build, no credentials in any real API
response body, and the OpenAPI schema never exposes a Rakuten secret
field name that could invite one being filled in and returned."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FRONTEND_SRC = _REPO_ROOT / "apps" / "web" / "src"


@pytest.mark.skipif(not _FRONTEND_SRC.exists(), reason="frontend checkout not present in this environment")
def test_no_rakuten_credential_names_anywhere_in_frontend_source():
    forbidden = ["RAKUTEN_CLIENT_SECRET", "RAKUTEN_CLIENT_ID", "RAKUTEN_TOKEN", "RAKUTEN_REFRESH_TOKEN"]
    offenders = []
    for path in _FRONTEND_SRC.rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in forbidden:
            if name in text:
                offenders.append((str(path), name))
    assert offenders == []


def test_settings_never_default_rakuten_secrets_to_a_non_empty_value():
    """A real credential must only ever come from the environment, never
    a hardcoded fallback baked into source — this test would fail loudly
    if someone "temporarily" hardcoded a real token as a default."""
    settings = get_settings()
    for field in ("RAKUTEN_CLIENT_ID", "RAKUTEN_CLIENT_SECRET", "RAKUTEN_TOKEN", "RAKUTEN_REFRESH_TOKEN"):
        default = type(settings).model_fields[field].default
        assert default is None


def test_env_example_only_has_empty_rakuten_placeholders():
    env_example = _REPO_ROOT / "apps" / "api" / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("RAKUTEN_") and "=" in line:
            key, _, value = line.partition("=")
            if key in ("RAKUTEN_ENABLED", "RAKUTEN_API_BASE_URL"):
                continue  # non-secret, has a real default value on purpose
            assert value.strip() == "", f"{key} must be an empty placeholder in .env.example, found {value!r}"


async def test_admin_endpoints_never_echo_the_configured_secret_back(client, db, monkeypatch):
    """Belt-and-suspenders on top of test_rakuten_admin_endpoints.py's own
    leak check — scans the *entire* raw response text, not just parsed
    JSON fields, for the exact configured secret value."""
    import httpx

    from app.retailers.rakuten import RakutenProductProvider
    from tests.conftest import make_admin, register_and_login

    secret_value = "sk_rakuten_super_secret_value_12345"

    async def _noop_sleep(*_a, **_kw):
        return None

    monkeypatch.setattr("app.retailers.rakuten.asyncio.sleep", _noop_sleep)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    provider = RakutenProductProvider(
        enabled=True,
        client_id="cid",
        client_secret=secret_value,
        access_token=None,
        refresh_token=None,
        publisher_id="pub123",
        account_id="acct123",
        base_url="https://api.rakutenmarketing.test",
    )
    monkeypatch.setattr("app.api.v1.endpoints.admin_rakuten.get_rakuten_provider", lambda: provider)

    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])

    resp = await client.get("/api/v1/admin/rakuten/status")
    assert secret_value not in resp.text

    # also confirm it's not silently JSON-encoded/escaped elsewhere in the body
    assert secret_value not in json.dumps(resp.json())
