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

# what each model in public/showcase/*-after.jpg wears (winter looks): the shop,
# its product id, and the search that finds it again
LOOKS: dict[str, list[dict]] = {
    "women": [
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
    ],
    "men": [
        {"name": "Charcoal wool double-breasted overcoat", "shop": "eBay", "r": "ebay", "id": "v1|820277076408|0",
         "q": "men charcoal wool overcoat", "price_cents": 12000, "currency": "usd",
         "image": "https://i.ebayimg.com/images/g/C1UAAeSwSiVq3lsJ/s-l1600.jpg"},
        {"name": "Polo Ralph Lauren cable-knit sweater", "shop": "eBay", "r": "ebay", "id": "v1|920001928938|0",
         "q": "men cream cable knit sweater", "price_cents": 9600, "currency": "usd",
         "image": "https://i.ebayimg.com/images/g/9sAAAeSwV71qwA-P/s-l1600.jpg"},
        {"name": "Maison Margiela ribbed wool scarf", "shop": "Giglio", "r": "rakuten", "id": "13578990",
         "q": "men grey wool scarf", "price_cents": 22500, "currency": "gbp",
         "image": "https://img.giglio.com/images/prodZoom/I24007.045_1.jpg"},
        {"name": "Brown leather Chelsea boots", "shop": "eBay", "r": "ebay", "id": "v1|336845329467|546159154638",
         "q": "men brown leather chelsea boots", "price_cents": 17546, "currency": "usd",
         "image": "https://i.ebayimg.com/images/g/oI0AAeSwRfNq0Le8/s-l1600.jpg"},
    ],
    "kids": [
        {"name": "Red hooded puffer jacket", "shop": "eBay", "r": "ebay", "id": "v1|407292784171|0",
         "q": "kids red puffer jacket", "price_cents": 1099, "currency": "usd",
         "image": "https://i.ebayimg.com/images/g/vu4AAeSwrGFq0QQI/s-l1600.jpg"},
        {"name": "Carhartt kids knit beanie", "shop": "eBay", "r": "ebay", "id": "v1|800840922201|0",
         "q": "kids knit beanie hat", "price_cents": 2999, "currency": "usd",
         "image": "https://i.ebayimg.com/images/g/9h0AAeSwtbBq32GM/s-l1600.jpg"},
        {"name": "Waterproof winter snow boots", "shop": "eBay", "r": "ebay", "id": "v1|303332402464|602417280993",
         "q": "boys black winter boots", "price_cents": 2499, "currency": "usd",
         "image": "https://i.ebayimg.com/images/g/dOgAAOSwnB5nGbff/s-l1600.jpg"},
    ],
}
LOOK = LOOKS["women"]
_CACHE_SECONDS = 6 * 3600
_cache: dict[str, tuple[float, list[ShowcaseItem]]] = {}


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
async def showcase_look(look: str = "women"):
    """The products in one of the example looks (women, men, kids), as the shops sell them now."""
    from fastapi import HTTPException, status

    items_spec = LOOKS.get(look)
    if items_spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown look")
    cached = _cache.get(look)
    if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    found = await asyncio.gather(*(_fresh(item) for item in items_spec))
    items = [i for i in found if i is not None]
    if not items:
        # no shop answered (keys missing, network): the saved details, links still work
        return [  # not cached: try the shops again next time
            ShowcaseItem(name=i["name"], shop=i["shop"], price_cents=i["price_cents"], currency=i["currency"],
                         image_url=i["image"], buy_url=_buy_url(i))
            for i in items_spec
        ]
    _cache[look] = (time.monotonic(), items)
    return items
