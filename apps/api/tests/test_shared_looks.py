"""Sharing a finished try-on as a public link, and stopping it."""

from __future__ import annotations

from app.ai.providers.base import TryOnOutput
from app.ai.providers.mock import MockTryOnProvider
from tests.conftest import register_and_login, seed_product, small_jpeg_bytes
from tests.test_tryon import _poll_until_terminal, _upload_front_photo


async def _finished_look(client, db, monkeypatch):  # noqa: ANN001, ANN202
    async def fake_generate(self, payload):  # noqa: ANN001, ANN202, ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Pink Embroidered Lehenga")
    job = (await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})).json()
    assert (await _poll_until_terminal(client, job["id"]))["status"] == "completed"
    return job["id"], product


async def test_the_owner_shares_and_anyone_with_the_link_sees_the_look(client, db, monkeypatch):  # noqa: ANN001
    job_id, product = await _finished_look(client, db, monkeypatch)

    shared = (await client.post(f"/api/v1/tryon/{job_id}/share")).json()
    assert shared["url"].endswith(f"/look/{shared['token']}")
    again = (await client.post(f"/api/v1/tryon/{job_id}/share")).json()
    assert again["token"] == shared["token"]  # one link per look

    await client.post("/api/v1/auth/logout")  # anyone, signed in or not
    page = await client.get(f"/api/v1/shared/{shared['token']}")
    assert page.status_code == 200
    body = page.json()
    assert body["title"] == "Pink Embroidered Lehenga"
    assert [p["id"] for p in body["products"]] == [product.id]
    assert "/affiliate/go/" in body["products"][0]["buy_url"]
    image = await client.get(f"/api/v1/shared/{shared['token']}/image")
    assert image.status_code == 200 and image.headers["content-type"].startswith("image/") and image.content


async def test_only_the_owner_can_share_and_stopping_hides_it(client, db, monkeypatch):  # noqa: ANN001
    job_id, _ = await _finished_look(client, db, monkeypatch)
    token = (await client.post(f"/api/v1/tryon/{job_id}/share")).json()["token"]

    owner_cookies = dict(client.cookies)
    await register_and_login(client)  # someone else
    assert (await client.post(f"/api/v1/tryon/{job_id}/share")).status_code == 404
    assert (await client.delete(f"/api/v1/tryon/{job_id}/share")).status_code == 404

    client.cookies.clear()
    for name, value in owner_cookies.items():
        client.cookies.set(name, value)
    assert (await client.delete(f"/api/v1/tryon/{job_id}/share")).status_code == 204
    assert (await client.get(f"/api/v1/shared/{token}")).status_code == 404
    assert (await client.get(f"/api/v1/shared/{token}/image")).status_code == 404


async def test_unknown_links_show_nothing(client):  # noqa: ANN001
    assert (await client.get("/api/v1/shared/not-a-real-link")).status_code == 404


async def test_a_visitor_tries_a_shared_outfit_on_themselves(client, db, monkeypatch):  # noqa: ANN001
    async def fake_generate(self, payload):  # noqa: ANN001, ANN202, ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    shirt = await seed_product(db, name="White Oxford Dress Shirt")
    chinos = await seed_product(db, name="Navy Slim Chino Pants")
    outfit = (
        await client.post(
            "/api/v1/outfits",
            json={"items": [{"product_id": shirt.id, "slot": "top"}, {"product_id": chinos.id, "slot": "bottom"}]},
        )
    ).json()
    job = (await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "outfit_id": outfit["id"]})).json()
    assert (await _poll_until_terminal(client, job["id"]))["status"] == "completed"
    token = (await client.post(f"/api/v1/tryon/{job['id']}/share")).json()["token"]

    await client.post("/api/v1/auth/logout")
    look = (await client.get(f"/api/v1/shared/{token}")).json()
    assert [p["id"] for p in look["products"]] == [shirt.id, chinos.id]
    assert look["total_cents"] == shirt.price_cents + chinos.price_cents
    assert (await client.post(f"/api/v1/shared/{token}/try")).status_code == 401  # an account is needed

    await register_and_login(client)  # the visitor signs up
    mine = (await client.post(f"/api/v1/shared/{token}/try")).json()
    assert mine["outfit_id"] and mine["outfit_id"] != outfit["id"]
    copy = (await client.get(f"/api/v1/outfits/{mine['outfit_id']}")).json()  # theirs, ready for their own photo
    assert [i["product"]["id"] for i in copy["items"]] == [shirt.id, chinos.id]


async def test_a_shared_single_product_look_opens_that_product(client, db, monkeypatch):  # noqa: ANN001
    job_id, product = await _finished_look(client, db, monkeypatch)
    token = (await client.post(f"/api/v1/tryon/{job_id}/share")).json()["token"]
    await register_and_login(client)
    assert (await client.post(f"/api/v1/shared/{token}/try")).json() == {"outfit_id": None, "product_id": product.id}
