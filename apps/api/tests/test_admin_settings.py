"""Admin-editable settings / API keys: admin-only, secrets are write-only
and encrypted at rest, changes take effect live (no restart), invalid or
non-whitelisted values are refused, and other processes pick up changes
from the database."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.runtime_settings import encrypt, refresh_if_stale
from app.models.app_setting import AppSetting
from tests.conftest import make_admin, register_and_login, seed_product, small_jpeg_bytes


@pytest_asyncio.fixture(autouse=True)
async def _clean_overrides(db):
    yield
    # never let an override (e.g. a fake FASHN key) leak into other test modules
    await db.execute(delete(AppSetting))
    await db.commit()
    await refresh_if_stale(force=True)


async def _admin(client, db) -> dict:
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])
    return data


def _field(body: dict, key: str) -> dict:
    return next(f for g in body["groups"] for f in g["fields"] if f["key"] == key)


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/v1/admin/settings"), ("put", "/api/v1/admin/settings"), ("post", "/api/v1/admin/settings/test/ai_tryon")],
)
async def test_settings_endpoints_are_admin_only(client, method, path):
    await register_and_login(client)
    kwargs = {"json": {"values": {}}} if method == "put" else {}
    assert (await getattr(client, method)(path, **kwargs)).status_code == 403


async def test_secret_is_write_only_masked_and_encrypted_at_rest(client, db):
    await _admin(client, db)
    secret = "fa-live-supersecret-value-9876"

    resp = await client.put("/api/v1/admin/settings", json={"values": {"FASHN_API_KEY": secret}})
    assert resp.status_code == 200, resp.text
    assert secret not in resp.text
    field = _field(resp.json(), "FASHN_API_KEY")
    assert field["value"] == "••••9876"
    assert field["source"] == "admin"

    row = (await db.execute(select(AppSetting).where(AppSetting.key == "FASHN_API_KEY"))).scalar_one()
    assert secret not in row.value_encrypted

    log = (await client.get("/api/v1/admin/audit-log")).json()["items"]
    entry = next(e for e in log if e["action"] == "settings.update")
    assert secret not in str(entry["detail"])

    assert get_settings().FASHN_API_KEY == secret


async def test_credit_cost_change_applies_live_and_reverts_to_env(client, db):
    await _admin(client, db)
    resp = await client.put("/api/v1/admin/settings", json={"values": {"TRYON_CREDIT_COST": "7"}})
    assert resp.status_code == 200
    assert _field(resp.json(), "TRYON_CREDIT_COST")["value"] == "7"

    files = {"file": ("front.jpg", small_jpeg_bytes(), "image/jpeg")}
    photo_id = (await client.post("/api/v1/photos", files=files, data={"kind": "front"})).json()["id"]
    product = await seed_product(db, name="Live Cost Product")
    job = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    assert job.status_code == 201, job.text
    assert job.json()["credit_cost"] == 7

    resp = await client.put("/api/v1/admin/settings", json={"values": {"TRYON_CREDIT_COST": None}})
    field = _field(resp.json(), "TRYON_CREDIT_COST")
    assert field["value"] == "5"
    assert field["source"] != "admin"


@pytest.mark.parametrize(
    ("values", "status_code"),
    [
        ({"TRYON_CREDIT_COST": "0"}, 400),
        ({"TRYON_CREDIT_COST": "cheap"}, 400),
        ({"FASHN_MODEL": "tryon-ultra"}, 400),
        ({"RAKUTEN_ENABLED": "maybe"}, 400),
        ({"DATABASE_URL": "sqlite:///elsewhere.db"}, 400),
        ({"SECRET_KEY": "new"}, 400),
    ],
)
async def test_invalid_or_non_whitelisted_values_are_refused(client, db, values, status_code):
    await _admin(client, db)
    resp = await client.put("/api/v1/admin/settings", json={"values": values})
    assert resp.status_code == status_code
    assert (await db.execute(select(AppSetting))).scalars().first() is None


async def test_choosing_a_real_provider_without_its_key_warns_instead_of_breaking(client, db):
    await _admin(client, db)
    resp = await client.put("/api/v1/admin/settings", json={"values": {"VIRTUAL_TRYON_PROVIDER": "fashn"}})
    assert resp.status_code == 200
    field = _field(resp.json(), "VIRTUAL_TRYON_PROVIDER")
    assert field["value"] == "mock"
    assert "missing" in field["warning"]


async def test_another_process_picks_up_a_change_written_to_the_database(db):
    """Simulates the RQ worker / a second API worker: the row is written
    directly (not through this process's endpoint), then the periodic
    refresh applies it."""
    db.add(AppSetting(key="OUTFIT_TRYON_CREDIT_COST", value_encrypted=encrypt("11")))
    await db.commit()
    await refresh_if_stale(force=True)
    assert get_settings().OUTFIT_TRYON_CREDIT_COST == 11


async def test_override_encrypted_with_an_old_secret_key_is_ignored_and_flagged(client, db):
    foreign = Fernet(Fernet.generate_key()).encrypt(b"3").decode()
    db.add(AppSetting(key="TRYON_CREDIT_COST", value_encrypted=foreign))
    await db.commit()

    await _admin(client, db)
    body = (await client.get("/api/v1/admin/settings")).json()
    field = _field(body, "TRYON_CREDIT_COST")
    assert field["unreadable"] is True
    assert get_settings().TRYON_CREDIT_COST == 5


async def test_connection_test_without_key_reports_mock_mode_without_network(client, db):
    await _admin(client, db)
    resp = await client.post("/api/v1/admin/settings/test/ai_tryon")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert "mock" in resp.json()["message"]

    # Amazon's adapter is written now, so the honest answer names what is
    # still missing rather than calling it an unbuilt integration
    resp = await client.post("/api/v1/admin/settings/test/amazon")
    assert resp.json()["ok"] is False
    assert "Associate ID" in resp.json()["message"]

    resp = await client.post("/api/v1/admin/settings/test/flipkart")
    assert resp.json()["ok"] is False
    assert "isn't built yet" in resp.json()["message"]

    assert (await client.post("/api/v1/admin/settings/test/database")).status_code == 404


@pytest.mark.parametrize(("fashn_status", "ok"), [(400, True), (401, False)])
async def test_fashn_connection_test_distinguishes_valid_and_rejected_keys(client, db, monkeypatch, fashn_status, ok):
    await _admin(client, db)
    secret = "fa-test-key-for-connection-check"
    await client.put("/api/v1/admin/settings", json={"values": {"FASHN_API_KEY": secret}})

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/run")
        assert request.headers["Authorization"] == f"Bearer {secret}"
        return httpx.Response(fashn_status, json={"error": "x", "message": f"echo {secret}"})

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    resp = await client.post("/api/v1/admin/settings/test/ai_tryon")
    assert resp.status_code == 200
    assert resp.json()["ok"] is ok
    assert secret not in resp.text


async def test_gemini_and_best_of_are_choosable_from_the_admin_panel(client, db):
    """Live bug: Gemini was wired into the app but never added to the
    admin panel's provider list, so the only way to switch to it — or to
    best_of, which needs both engines' keys set here too — was editing
    .env directly on the server and restarting."""
    await _admin(client, db)
    resp = await client.get("/api/v1/admin/settings")
    field = _field(resp.json(), "VIRTUAL_TRYON_PROVIDER")
    assert {"gemini", "best_of"} <= set(field["choices"])
    assert any(f["key"] == "GEMINI_API_KEY" for group in resp.json()["groups"] for f in group["fields"])


async def test_best_of_warns_by_name_for_each_missing_key(client, db):
    """Both keys missing names both of them, not a fixed phrase written
    for the single-key providers this warning used to be hardcoded to."""
    await _admin(client, db)
    resp = await client.put("/api/v1/admin/settings", json={"values": {"VIRTUAL_TRYON_PROVIDER": "best_of"}})
    assert resp.status_code == 200
    field = _field(resp.json(), "VIRTUAL_TRYON_PROVIDER")
    assert field["value"] == "mock"
    assert "OpenAI API key" in field["warning"] and "Gemini API key" in field["warning"]


async def test_best_of_falls_back_to_the_engine_that_still_has_a_key(client, db):
    await _admin(client, db)
    await client.put("/api/v1/admin/settings", json={"values": {"OPENAI_API_KEY": "sk-test-key"}})
    resp = await client.put("/api/v1/admin/settings", json={"values": {"VIRTUAL_TRYON_PROVIDER": "best_of"}})
    assert resp.status_code == 200
    field = _field(resp.json(), "VIRTUAL_TRYON_PROVIDER")
    assert field["value"] == "openai"  # only one of the two keys is set
    assert "missing" in field["warning"]
