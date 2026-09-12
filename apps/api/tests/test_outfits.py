"""Outfit endpoints: manual creation gets a real compatibility score (not
just grouped products), the preview endpoint scores without persisting,
and access is scoped to the owning user."""

from __future__ import annotations

from tests.conftest import register_and_login, seed_product


async def test_create_outfit_computes_a_compatibility_score(client, db):
    top = await seed_product(db, name="Black Tee", color="black", style_tags=["casual"])
    bottom = await seed_product(db, name="Black Jeans", color="black", style_tags=["casual"])
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/outfits",
        json={"items": [{"product_id": top.id, "slot": "top"}, {"product_id": bottom.id, "slot": "bottom"}]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["compatibility_score"] is not None
    assert 0 <= body["compatibility_score"] <= 100
    assert body["total_price_cents"] == top.price_cents + bottom.price_cents


async def test_create_outfit_rejects_unknown_product(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/outfits", json={"items": [{"product_id": "does-not-exist", "slot": "top"}]})
    assert resp.status_code == 404


async def test_preview_compatibility_does_not_persist_an_outfit(client, db):
    top = await seed_product(db, name="Preview Top", color="red", style_tags=["formal"])
    bottom = await seed_product(db, name="Preview Bottom", color="green", style_tags=["athleisure"])
    await register_and_login(client)

    resp = await client.post(
        "/api/v1/outfits/preview-compatibility",
        json={"items": [{"product_id": top.id, "slot": "top"}, {"product_id": bottom.id, "slot": "bottom"}]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "overall" in body and "notes" in body

    listed = await client.get("/api/v1/outfits")
    assert listed.json() == []


async def test_outfit_access_is_scoped_to_owner(client, db):
    product = await seed_product(db)
    await register_and_login(client)
    created = await client.post("/api/v1/outfits", json={"items": [{"product_id": product.id, "slot": "top"}]})
    outfit_id = created.json()["id"]

    await register_and_login(client)  # a different user
    resp = await client.get(f"/api/v1/outfits/{outfit_id}")
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/outfits/{outfit_id}")
    assert resp.status_code == 404


async def test_stylist_auto_generated_outfit_also_has_a_compatibility_score(client, db):
    await seed_product(db, name="Stylist Top", color="black", style_tags=["casual"])
    await seed_product(db, name="Stylist Bottom", color="black", style_tags=["casual"])
    await register_and_login(client)

    resp = await client.post("/api/v1/stylist/ask", json={"prompt": "casual black outfit", "max_items": 5})
    assert resp.status_code == 200
    body = resp.json()
    if body["outfit"]:
        assert body["outfit"]["compatibility_score"] is not None
