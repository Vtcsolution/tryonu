"""Where a shopper likes to shop (asked once after signing up): local shops
first, worldwide stores first, or both. It changes the order of search
results, never hides any."""

from __future__ import annotations

import pytest

from app.services.live_search_service import _local_stores_first
from app.services.shopper_context import set_country, set_shop_from
from tests.conftest import register_and_login
from tests.test_store_recommended import _r


@pytest.fixture(autouse=True)
def _reset():  # noqa: ANN202
    yield
    set_country(None)
    set_shop_from(None)


def _results():  # noqa: ANN202
    return [
        _r("ebay", "ebay"),
        _r("stores", "store_uk", country="GB"),
        _r("daraz", "daraz"),
        _r("stores", "store_pk", country="PK"),
        _r("aliexpress", "ali"),
    ]


def _order() -> list[str]:
    return [r.raw.retailer_product_id for r in _local_stores_first(_results())]


def test_local_puts_shops_in_my_country_first():
    set_country("PK")
    set_shop_from("local")
    assert _order() == ["store_pk", "daraz", "store_uk", "ebay", "ali"]


def test_worldwide_puts_international_websites_first():
    set_country("PK")
    set_shop_from("worldwide")
    assert _order() == ["ebay", "ali", "store_uk", "store_pk", "daraz"]


def test_both_keeps_the_usual_order_and_nothing_is_ever_hidden():
    set_country("PK")
    set_shop_from("both")
    usual = _order()
    assert usual[:2] in (["store_pk", "store_uk"], ["store_uk", "store_pk"])  # TryOnU shops first, as before
    set_shop_from(None)
    assert _order() == usual
    for choice in ("local", "worldwide"):
        set_shop_from(choice)
        assert sorted(_order()) == sorted(usual)


async def test_the_choice_is_saved_with_the_profile(client):  # noqa: ANN001
    await register_and_login(client)
    assert (await client.get("/api/v1/users/me/preferences")).json()["shop_from"] is None
    saved = await client.put("/api/v1/users/me/preferences", json={"shop_from": "local"})
    assert saved.status_code == 200 and saved.json()["shop_from"] == "local"
    assert (await client.put("/api/v1/users/me/preferences", json={"shop_from": "moon"})).status_code == 422
