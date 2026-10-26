"""The home page's example look: the real shop products in the slider's
"After try-on" picture, with their current price and picture, fetched live
from the shops (cached for a few hours). A product a shop no longer sells is
left out by itself."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlencode

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import logger

router = APIRouter(prefix="/showcase", tags=["showcase"])

# what the model in public/showcase/studio-after.jpg wears: the shop, its
# product id, and the search that finds it again
LOOK: list[dict] = [
    {"name": "Max Mara jersey midi dress", "shop": "Giglio", "r": "rakuten", "id": "13639623", "q": "women black midi dress",
     "price_cents": 24000, "currency": "gbp", "image": "https://img.giglio.com/images/prodZoom/I35070.002_1.jpg"},
    {"name": "Camel double-breasted long coat", "shop": "eBay", "r": "ebay", "id": "v1|397232866979|665629854938",
     "q": "women camel wool long coat", "price_cents": 5769, "currency": "usd",
     "image": "https://i.ebayimg.com/images/g/za0AAeSwp0RpSKM2/s-l1600.jpg"},
    {"name": "Naturalizer black leather ankle boots", "shop": "eBay", "r": "ebay", "id": "v1|278445526745|2561029494610",
     "q": "women black leather ankle boots", "price_cents": 4999, "currency": "usd",
     "image": "https://i.ebayimg.com/images/g/AOQAAeSw3JVq2UD~/s-l1600.jpg"},
    {"name": "Chloé leather bracelet bag", "shop": "Giglio", "r": "rakuten", "id": "13617007", "q": "women tan leather handbag",
     "price_cents": 146250, "currency": "gbp", "image": "https://img.giglio.com/images/prodZoom/I31201.032_1.jpg"},
]
_CACHE_SECONDS = 6 * 3600
_cache: tuple[float, list[ShowcaseItem]] | None = None


class ShowcaseItem(BaseModel):
    name: str
    shop: str
    price_cents: int
    currency: str
    image_url: str
    # opens the shop through TryOnU (click counted, affiliate link)
    buy_url: str


def _buy_url(item: dict) -> str:
    api = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
    return f"{api}/api/v1/affiliate/live?{urlencode({'r': item['r'], 'id': item['id'], 'q': item['q'], 'source': 'product_card'})}"


async def _fresh(item: dict) -> ShowcaseItem | None:
    from app.services.live_search_service import find_live_result

    try:
        result = await find_live_result(item["q"], retailer_slug=item["r"], retailer_product_id=item["id"])
    except Exception as exc:  # noqa: BLE001 - one shop being down must not empty the list
        logger.warning("showcase_item_failed", item=item["name"], error=str(exc)[:200])
        return None
    if result is None or (result.raw.price_cents or 0) <= 0:
        return None
    return ShowcaseItem(
        name=item["name"],
        shop=item["shop"],  # the short name ("Giglio", not "GIGLIO.COM s.p.a (Global)")
        price_cents=result.raw.price_cents,
        currency=result.raw.currency or item["currency"],
        image_url=(result.raw.images or [item["image"]])[0],
        buy_url=_buy_url(item),
    )


@router.get("/look", response_model=list[ShowcaseItem])
async def showcase_look():
    """The products in the home page's example look, as the shops sell them now."""
    global _cache  # noqa: PLW0603 - one small per-process cache
    if _cache and time.monotonic() - _cache[0] < _CACHE_SECONDS:
        return _cache[1]
    found = await asyncio.gather(*(_fresh(item) for item in LOOK))
    items = [i for i in found if i is not None]
    if not items:
        # no shop answered (keys missing, network): the saved details, links still work
        items = [
            ShowcaseItem(name=i["name"], shop=i["shop"], price_cents=i["price_cents"], currency=i["currency"],
                         image_url=i["image"], buy_url=_buy_url(i))
            for i in LOOK
        ]
        return items  # not cached: try the shops again next time
    _cache = (time.monotonic(), items)
    return items
