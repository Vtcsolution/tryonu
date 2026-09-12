"""Rakuten in the real catalog ingestion pipeline (services/
product_ingestion_service.py) — disabled has zero effect on the rest of
the sync, enabled+mocked correctly upserts real rows including the new
merchant_name/merchant_id fields, and re-running doesn't duplicate."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.models.product import Product
from app.models.retailer import Retailer
from app.retailers.rakuten import RakutenProductProvider
from app.services.product_ingestion_service import sync_all_retailers


@pytest.fixture(autouse=True)
def _skip_real_throttle_sleep(monkeypatch):
    async def _noop_sleep(*_a, **_kw):
        return None

    monkeypatch.setattr("app.retailers.rakuten.asyncio.sleep", _noop_sleep)


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _disabled_provider() -> RakutenProductProvider:
    return RakutenProductProvider(
        enabled=False,
        client_id=None,
        client_secret=None,
        access_token=None,
        refresh_token=None,
        publisher_id=None,
        account_id=None,
        base_url="https://api.rakutenmarketing.test",
    )


def _enabled_provider() -> RakutenProductProvider:
    return RakutenProductProvider(
        enabled=True,
        client_id="cid",
        client_secret="csecret",
        access_token=None,
        refresh_token=None,
        publisher_id="pub123",
        account_id="acct123",
        base_url="https://api.rakutenmarketing.test",
    )


async def test_disabled_rakuten_has_zero_effect_on_the_rest_of_the_sync(db, monkeypatch):
    """The DB is shared across the whole test session, so this asserts the
    *change* from one disabled-Rakuten-only sync is zero — not that the
    table is empty (other tests' rows are already in it)."""
    monkeypatch.setattr(
        "app.services.product_ingestion_service.get_all_providers", lambda: [_disabled_provider()]
    )

    before = len((await db.execute(select(Product))).scalars().all())
    results = await sync_all_retailers(db, limit_per_retailer=10)
    assert "rakuten" not in results  # skipped, not synced-with-zero

    after = len((await db.execute(select(Product))).scalars().all())
    assert after == before  # nothing written


_INGEST_ITEM_XML = (
    "<item><sku>RKT-INGEST-1</sku><productname>Ingestion Test Dress</productname>"
    "<brandname>Test Brand</brandname><merchantname>Test Merchant</merchantname><mid>999</mid>"
    '<price currency="USD">25.00</price><linkurl>https://click.example/deeplink?mid=999</linkurl>'
    "<imageurl>https://img.example/dress.jpg</imageurl></item>"
)


async def test_enabled_rakuten_upserts_real_rows_with_merchant_fields(db, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=f"<result><TotalMatches>1</TotalMatches>{_INGEST_ITEM_XML}</result>")

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(
        "app.services.product_ingestion_service.get_all_providers", lambda: [_enabled_provider()]
    )

    results = await sync_all_retailers(db, limit_per_retailer=5)
    assert results.get("rakuten") == 1

    retailer = (await db.execute(select(Retailer).where(Retailer.slug == "rakuten"))).scalar_one()
    assert retailer.name == "Rakuten Advertising"

    product = (
        await db.execute(select(Product).where(Product.retailer_product_id == "RKT-INGEST-1"))
    ).scalar_one()
    assert product.name == "Ingestion Test Dress"
    assert product.merchant_name == "Test Merchant"
    assert product.merchant_id == "999"
    assert product.price_cents == 2500
    assert product.affiliate_url == "https://click.example/deeplink?mid=999"


async def test_reingesting_the_same_rakuten_product_does_not_duplicate(db, monkeypatch):
    item_xml = (
        "<item><sku>RKT-DEDUPE-1</sku><productname>Dedupe Test Item</productname><mid>1</mid>"
        '<price currency="USD">10.00</price><linkurl>https://click.example/deeplink?mid=1</linkurl></item>'
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, text=f"<result><TotalMatches>1</TotalMatches>{item_xml}</result>")

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(
        "app.services.product_ingestion_service.get_all_providers", lambda: [_enabled_provider()]
    )

    await sync_all_retailers(db, limit_per_retailer=5)
    await sync_all_retailers(db, limit_per_retailer=5)  # run again

    rows = (
        await db.execute(select(Product).where(Product.retailer_product_id == "RKT-DEDUPE-1"))
    ).scalars().all()
    assert len(rows) == 1  # upserted, not duplicated


async def test_rakuten_sync_failure_does_not_abort_other_retailers(db, monkeypatch):
    """A live Rakuten API error must not take down the whole sync — same
    resilience guarantee already relied on for eBay/CJ."""
    from app.retailers.sample import SampleCatalogProvider

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(503, text="down")

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(
        "app.services.product_ingestion_service.get_all_providers",
        lambda: [_enabled_provider(), SampleCatalogProvider()],
    )

    results = await sync_all_retailers(db, limit_per_retailer=5)
    assert "rakuten" not in results
    assert results.get("sample") == 5  # capped by limit_per_retailer, same as any other retailer
