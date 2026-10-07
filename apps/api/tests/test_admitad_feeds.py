"""Admitad feed import and search. Offline: feeds are served by httpx.MockTransport."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import delete, func, select

from app.models.admitad_feed import AdmitadFeedItem
from app.retailers.admitad import AdmitadFeedProvider
from app.services import admitad_feeds
from app.services.admitad_feeds import import_campaign, normalize_row, parse_price, search_feed

_YML = (
    "available,categoryId,currencyId,description,id,name,oldprice,picture,price,url,vendor\n"
    'true,12,USD,"A satin dress, midi length",a1,Black Satin Midi Dress,79.00,https://img.example/a1.jpg,54.99,https://dorinebeaumont.com/g/x/?ulp=a1,Allegra K\n'
    "true,13,USD,,a2,Gold Hoop Earrings,,https://img.example/a2.jpg,12.50,https://dorinebeaumont.com/g/x/?ulp=a2,Allegra K\n"
    "false,14,USD,,a3,Red Party Dress,,https://img.example/a3.jpg,40.00,https://dorinebeaumont.com/g/x/?ulp=a3,Allegra K\n"
    "true,15,USD,,a4,No Picture Dress,,,40.00,https://dorinebeaumont.com/g/x/?ulp=a4,Allegra K\n"
)
_GOOGLE = (
    "id\ttitle\tlink\timage_link\tprice\tsale_price\tavailability\tproduct_type\n"
    "g1\tFloral Wrap Dress\thttps://rzekl.com/g/y/?ulp=g1\thttps://img.example/g1.jpg\t30.00 USD\t25.99 USD\tin stock\tApparel\n"
)


def _campaign(feeds):  # noqa: ANN001, ANN202
    return {"id": 38910, "name": "Allegra K Many GEOs", "feeds_info": feeds}


def _feed(name, link, days_old=0):  # noqa: ANN001, ANN202
    stamp = (datetime.now(timezone.utc) - timedelta(days=days_old)).strftime("%Y-%m-%d %H:%M:%S")
    return {"name": name, "csv_link": link, "advertiser_last_update": stamp}


def _feeds(files: dict[str, tuple[int, str]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        status, body = files[str(request.url)]
        return httpx.Response(status, text=body)

    return httpx.MockTransport(handler)


@pytest.fixture
async def clean(db):  # noqa: ANN001, ANN201
    await db.execute(delete(AdmitadFeedItem))
    await db.commit()
    return db


def test_prices_in_every_shape_a_feed_writes_them():
    assert parse_price("54.99") == 5499
    assert parse_price("25.99 USD") == 2599
    assert parse_price("1,299.00") == 129900
    assert parse_price("12,50") == 1250
    assert parse_price("") is None and parse_price("0") is None


def test_both_feed_layouts_become_the_same_product_fields():
    yml = normalize_row(
        {"id": "a1", "name": "Black Satin Midi Dress", "url": "https://t/a1", "picture": "https://i/a1.jpg",
         "price": "54.99", "oldprice": "79.00", "currencyId": "USD", "vendor": "Allegra K", "available": "true"},
        38910, "Allegra K Many GEOs",
    )
    assert yml["price_cents"] == 5499 and yml["old_price_cents"] == 7900 and yml["currency"] == "usd"
    google = normalize_row(
        {"id": "g1", "title": "Floral Wrap Dress", "link": "https://t/g1", "image_link": "https://i/g1.jpg",
         "price": "30.00 USD", "sale_price": "25.99 USD", "availability": "in stock"},
        20881, "Alibaba WW",
    )
    assert google["price_cents"] == 2599 and google["old_price_cents"] == 3000 and google["currency"] == "usd"
    assert normalize_row({"id": "x", "name": "No link"}, 1, "x") is None


async def test_a_programme_is_imported_from_its_fresh_feeds_only(clean):  # noqa: ANN001
    campaign = _campaign([_feed("Main", "https://feeds.test/main"), _feed("Old", "https://feeds.test/old", days_old=400)])
    report = await import_campaign(clean, campaign, transport=_feeds({"https://feeds.test/main": (200, _YML), "https://feeds.test/old": (200, _GOOGLE)}))

    assert report.feeds_used == ["Main"] and report.feeds_stale == ["Old"]
    assert report.rows_kept == 3 and report.rows_skipped == 1  # the row without a picture
    names = set((await clean.execute(select(AdmitadFeedItem.name))).scalars())
    assert names == {"Black Satin Midi Dress", "Gold Hoop Earrings", "Red Party Dress"}
    dress = (await clean.execute(select(AdmitadFeedItem).where(AdmitadFeedItem.offer_id == "a1"))).scalar_one()
    assert dress.product_url == "https://dorinebeaumont.com/g/x/?ulp=a1"  # the tracked link, untouched


async def test_a_failed_download_keeps_yesterdays_products(clean):  # noqa: ANN001
    campaign = _campaign([_feed("Main", "https://feeds.test/main")])
    await import_campaign(clean, campaign, transport=_feeds({"https://feeds.test/main": (200, _YML)}))
    with pytest.raises(RuntimeError):
        await import_campaign(clean, campaign, transport=_feeds({"https://feeds.test/main": (503, "down")}))
    await clean.rollback()
    assert (await clean.execute(select(func.count()).select_from(AdmitadFeedItem))).scalar() == 3


async def test_search_narrows_from_the_front_and_keeps_the_item(clean, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(admitad_feeds.get_settings(), "ADMITAD_FEED_MAX_AGE_DAYS", 180)
    await import_campaign(clean, _campaign([_feed("Main", "https://feeds.test/main")]), transport=_feeds({"https://feeds.test/main": (200, _YML)}))

    exact = await search_feed(clean, "women black satin midi dress", 10)
    assert [i.name for i in exact] == ["Black Satin Midi Dress"]
    loose = await search_feed(clean, "women emerald velvet party dress", 10)
    assert [i.name for i in loose] == ["Red Party Dress"]  # "velvet" and "emerald" dropped, "party dress" kept
    assert await search_feed(clean, "men leather boots", 10) == []


async def test_the_admitad_source_names_the_shop_and_keeps_its_link(clean):  # noqa: ANN001
    await import_campaign(clean, _campaign([_feed("Main", "https://feeds.test/main")]), transport=_feeds({"https://feeds.test/main": (200, _YML)}))
    provider = AdmitadFeedProvider()

    found = await provider.search_live(query="gold hoop earrings", limit=5)
    assert len(found) == 1
    raw = found[0]
    assert raw.merchant_name == "Allegra K Many GEOs" and raw.retailer_product_id == "38910:a2"
    assert provider.build_affiliate_url(raw.product_url, tracking_tag="tryonu-20") == raw.product_url
    again = await provider.fetch_by_id("38910:a2")
    assert again is not None and again.name == "Gold Hoop Earrings"
    assert await provider.fetch_products() == []


async def test_a_huge_feed_stops_downloading_at_the_product_limit(clean, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(admitad_feeds.get_settings(), "ADMITAD_FEED_MAX_ROWS", 2)
    report = await import_campaign(
        clean, _campaign([_feed("Main", "https://feeds.test/main")]), transport=_feeds({"https://feeds.test/main": (200, _YML)})
    )
    assert report.capped and report.rows_kept == 2
