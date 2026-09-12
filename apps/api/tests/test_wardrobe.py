"""Digital wardrobe: CRUD scoped strictly to the owning user, plus the
optional photo attach/replace flow (reuses the same storage pattern as
UserPhoto)."""

from __future__ import annotations

from tests.conftest import register_and_login, small_jpeg_bytes


async def test_create_list_update_and_delete_a_wardrobe_item(client):
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/wardrobe",
        json={"name": "Black Trousers", "category": "bottoms", "color": "black", "style_tags": ["formal"]},
    )
    assert resp.status_code == 201, resp.text
    item = resp.json()
    assert item["name"] == "Black Trousers"
    assert item["image_url"] is None

    resp = await client.get("/api/v1/wardrobe")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.patch(f"/api/v1/wardrobe/{item['id']}", json={"color": "charcoal"})
    assert resp.status_code == 200
    assert resp.json()["color"] == "charcoal"

    resp = await client.delete(f"/api/v1/wardrobe/{item['id']}")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/wardrobe")
    assert resp.json() == []


async def test_wardrobe_photo_upload_and_replace(client):
    await register_and_login(client)
    item = (await client.post("/api/v1/wardrobe", json={"name": "Denim Jacket"})).json()

    files = {"file": ("jacket.jpg", small_jpeg_bytes(), "image/jpeg")}
    resp = await client.post(f"/api/v1/wardrobe/{item['id']}/photo", files=files)
    assert resp.status_code == 200, resp.text
    first_url = resp.json()["image_url"]
    assert first_url

    # uploading again replaces the photo, doesn't error or duplicate
    files = {"file": ("jacket2.jpg", small_jpeg_bytes(color=(10, 20, 30)), "image/jpeg")}
    resp = await client.post(f"/api/v1/wardrobe/{item['id']}/photo", files=files)
    assert resp.status_code == 200
    assert resp.json()["image_url"]


async def test_wardrobe_items_are_scoped_to_owner(client):
    await register_and_login(client)
    item = (await client.post("/api/v1/wardrobe", json={"name": "Owner Only Item"})).json()

    await register_and_login(client)  # a different user
    resp = await client.patch(f"/api/v1/wardrobe/{item['id']}", json={"color": "red"})
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/wardrobe/{item['id']}")
    assert resp.status_code == 404

    files = {"file": ("x.jpg", small_jpeg_bytes(), "image/jpeg")}
    resp = await client.post(f"/api/v1/wardrobe/{item['id']}/photo", files=files)
    assert resp.status_code == 404

    resp = await client.get("/api/v1/wardrobe")
    assert resp.json() == []


async def test_create_wardrobe_item_requires_a_name(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/wardrobe", json={"name": ""})
    assert resp.status_code == 422
