"""Saved looks: save/list/delete a try-on result, scoped strictly to the
owning user — including the ownership check on save() itself (a real gap
found while wiring the frontend: nothing previously stopped one user from
saving another user's try-on result by guessing its id)."""

from __future__ import annotations

from app.ai.providers.base import TryOnOutput
from app.ai.providers.mock import MockTryOnProvider
from tests.conftest import register_and_login, seed_product, small_jpeg_bytes
from tests.test_tryon import _poll_until_terminal, _upload_front_photo


async def _complete_a_tryon(client, db, monkeypatch) -> dict:
    async def fake_generate(self, payload):  # noqa: ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)

    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Saveable Product")
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    job = await _poll_until_terminal(client, resp.json()["id"])
    assert job["status"] == "completed"
    return job


async def test_save_list_and_delete_a_look(client, db, monkeypatch):
    await register_and_login(client)
    job = await _complete_a_tryon(client, db, monkeypatch)
    result_id = job["result"]["id"]

    resp = await client.post(f"/api/v1/users/me/saved-looks/{result_id}", params={"title": "Date night"})
    assert resp.status_code == 201, resp.text
    look_id = resp.json()["id"]

    resp = await client.get("/api/v1/users/me/saved-looks")
    assert resp.status_code == 200
    looks = resp.json()
    assert len(looks) == 1
    assert looks[0]["id"] == look_id
    assert looks[0]["title"] == "Date night"
    assert looks[0]["image_url"] == job["result"]["image_url"]
    assert looks[0]["product"]["name"] == "Saveable Product"

    resp = await client.delete(f"/api/v1/users/me/saved-looks/{look_id}")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/users/me/saved-looks")
    assert resp.json() == []


async def test_cannot_save_another_users_tryon_result(client, db, monkeypatch):
    await register_and_login(client)
    job = await _complete_a_tryon(client, db, monkeypatch)
    result_id = job["result"]["id"]

    # a second, different user tries to save the first user's result
    await register_and_login(client)
    resp = await client.post(f"/api/v1/users/me/saved-looks/{result_id}")
    assert resp.status_code == 404

    resp = await client.get("/api/v1/users/me/saved-looks")
    assert resp.json() == []


async def test_save_nonexistent_result_is_404(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/users/me/saved-looks/does-not-exist")
    assert resp.status_code == 404


async def test_delete_another_users_saved_look_is_404(client, db, monkeypatch):
    await register_and_login(client)
    job = await _complete_a_tryon(client, db, monkeypatch)
    result_id = job["result"]["id"]
    look_id = (await client.post(f"/api/v1/users/me/saved-looks/{result_id}")).json()["id"]

    await register_and_login(client)
    resp = await client.delete(f"/api/v1/users/me/saved-looks/{look_id}")
    assert resp.status_code == 404
