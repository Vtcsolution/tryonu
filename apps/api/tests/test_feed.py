"""Onboarding category tree and the personalised "For you" feed."""

from __future__ import annotations

import uuid

import pytest_asyncio

from app.core.taxonomy import AUDIENCES, NODES, feed_nodes, normalize_selection
from app.models.product import Product
from app.models.retailer import Retailer
from app.retailers.base import ProductProvider, RawProduct
from app.services import feed_service
from app.services.live_search_service import LiveSearchResult
from tests.conftest import register_and_login


class _Provider(ProductProvider):
    def __init__(self, slug: str):
        self.slug = slug
        self.display_name = slug.title()

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:  # pragma: no cover
        return []


@pytest_asyncio.fixture(autouse=True)
async def _fresh_cache():
    feed_service._cache.clear()
    yield
    feed_service._cache.clear()


def _patch_search(monkeypatch, slug: str, catalog: dict[str, list[tuple[str, int]]], calls: list[str] | None = None):
    provider = _Provider(slug)

    async def fake_live_search(query: str, *, limit: int = 24):
        if calls is not None:
            calls.append(query)
        return [
            LiveSearchResult(
                provider=provider,
                raw=RawProduct(
                    retailer_product_id=pid,
                    name=f"{query} {pid}",
                    price_cents=price,
                    product_url=f"https://example.com/{pid}",
                    images=["https://example.com/i.jpg"],
                ),
            )
            for pid, price in catalog.get(query, [])
        ]

    monkeypatch.setattr("app.services.feed_service.live_search", fake_live_search)
    return provider


# ------------------------------------------------------------------ taxonomy


def test_every_category_has_a_search_phrase_and_unique_id():
    assert {a.id for a in AUDIENCES} == {"w", "m", "k"}
    assert all(node.search.strip() for node in NODES.values())


def test_feed_uses_the_most_specific_pick():
    picks = ["w", "w.jewellery", "w.jewellery.bangles", "w.jewellery.bangles.kundan", "w.shoes", "nope"]
    assert [n.id for n in feed_nodes(picks)] == ["w.jewellery.bangles.kundan", "w.shoes"]


def test_unknown_ids_are_dropped():
    assert normalize_selection(["w.shoes", "w.shoes", "made.up"]) == ["w.shoes"]


async def test_taxonomy_endpoint_is_public(client):
    resp = await client.get("/api/v1/catalog/taxonomy")
    assert resp.status_code == 200
    women = next(a for a in resp.json()["audiences"] if a["id"] == "w")
    jewellery = next(c for c in women["children"] if c["id"] == "w.jewellery")
    bangles = next(c for c in jewellery["children"] if c["id"] == "w.jewellery.bangles")
    assert {c["label"] for c in bangles["children"]} >= {"Kundan", "Glass (churi)"}
    assert "search" not in str(resp.json())  # internal search phrases aren't exposed


async def test_saving_categories_keeps_only_known_ids(client):
    await register_and_login(client)
    resp = await client.put(
        "/api/v1/users/me/preferences",
        json={"gender": "women", "preferred_categories": ["w", "w.shoes.khussa", "hacked.id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["preferred_categories"] == ["w", "w.shoes.khussa"]


# ------------------------------------------------------------------ feed


async def test_for_you_mixes_picked_categories_within_budget(client, monkeypatch):
    calls: list[str] = []
    _patch_search(
        monkeypatch,
        f"shop-{uuid.uuid4().hex[:6]}",
        {
            "kundan bangles": [("b1", 1500), ("b2", 2500), ("b3", 99_900)],
            "khussa": [("k1", 3000), ("k2", 4000)],
        },
        calls,
    )
    await register_and_login(client)
    await client.put(
        "/api/v1/users/me/preferences",
        json={
            "preferred_categories": ["w", "w.jewellery", "w.jewellery.bangles", "w.jewellery.bangles.kundan", "w.shoes", "w.shoes.khussa"],
            "budget_max_cents": 5000,
        },
    )

    resp = await client.get("/api/v1/feed/for-you")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [(s["id"], s["label"], s["parent_label"]) for s in body["sections"]] == [
        ("w.jewellery.bangles.kundan", "Kundan", "Bangles"),
        ("w.shoes.khussa", "Khussa", "Shoes"),
    ]
    ids = [i["retailer_product_id"] for i in body["items"]]
    assert ids == ["b1", "k1", "b2", "k2"]  # interleaved; b3 is over budget
    assert body["items"][0]["search_term"] == "kundan bangles"  # lets /products/select-live re-find it
    assert body["items"][0]["category_id"] == "w.jewellery.bangles.kundan"

    # one category at a time, and the cache avoids a second retailer call
    resp = await client.get("/api/v1/feed/for-you", params={"node": "w.shoes.khussa"})
    assert [i["retailer_product_id"] for i in resp.json()["items"]] == ["k1", "k2"]
    assert calls.count("khussa") == 1


async def test_for_you_rejects_unknown_or_audience_level_nodes(client, monkeypatch):
    _patch_search(monkeypatch, "shop-x", {})
    await register_and_login(client)
    assert (await client.get("/api/v1/feed/for-you", params={"node": "nope"})).status_code == 404
    assert (await client.get("/api/v1/feed/for-you", params={"node": "w"})).status_code == 404


async def test_for_you_without_picks_is_empty_and_requires_login(client, monkeypatch):
    _patch_search(monkeypatch, "shop-y", {})
    assert (await client.get("/api/v1/feed/for-you")).status_code == 401
    await register_and_login(client)
    body = (await client.get("/api/v1/feed/for-you")).json()
    assert body == {"sections": [], "active": None, "items": []}


async def test_admin_hidden_product_stays_hidden_even_from_cache(client, db, monkeypatch):
    slug = f"shop-{uuid.uuid4().hex[:6]}"
    _patch_search(monkeypatch, slug, {"khussa": [("keep", 1000), ("hide-me", 1000)]})
    await register_and_login(client)
    await client.put("/api/v1/users/me/preferences", json={"preferred_categories": ["w.shoes.khussa"]})
    first = (await client.get("/api/v1/feed/for-you")).json()
    assert {i["retailer_product_id"] for i in first["items"]} == {"keep", "hide-me"}

    retailer = Retailer(slug=slug, name="Shop")
    db.add(retailer)
    await db.flush()
    db.add(Product(retailer_id=retailer.id, retailer_product_id="hide-me", name="x", price_cents=1000,
                   product_url="https://example.com", affiliate_url="https://example.com", is_active=False))
    await db.commit()

    again = (await client.get("/api/v1/feed/for-you")).json()  # served from cache
    assert [i["retailer_product_id"] for i in again["items"]] == ["keep"]
