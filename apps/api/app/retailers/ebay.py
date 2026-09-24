"""eBay Browse API adapter — real product search, no affiliate approval
required to activate (eBay Partner Network affiliate tracking can be
layered on separately once/if pursued; see build_affiliate_url below).

Auth: OAuth2 client-credentials grant against
  POST https://api.ebay.com/identity/v1/oauth2/token
using EBAY_CLIENT_ID / EBAY_CLIENT_SECRET (from a Browse API keyset —
https://developer.ebay.com/my/keys), scope `https://api.ebay.com/oauth/api_scope`.

Products: the Browse API has no generic "all fashion" browse endpoint —
every call is a keyword search, so this walks a fixed list of fashion
category terms (item_summary/search) and pages each until `limit` is
reached or the term's results run out.
"""

from __future__ import annotations

import re
import time

import httpx

from app.core.logging import logger
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError

_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
_ITEM_URL = "https://api.ebay.com/buy/browse/v1/item"  # /{itemId} — the id search already gives us
_OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"
_PAGE_SIZE = 50

# eBay's Browse API returns image.imageUrl at "s-l225" (225px) — a real
# thumbnail, not remotely HD. eBay's own CDN serves the exact same photo at
# multiple fixed sizes from the same path (confirmed live: swapping the
# size segment returns 200, not a 404), and "s-l1600" is the largest it
# offers — used for our try-on garment image, this is the size actually
# composited onto the user's photo, so a blurry source directly meant a
# blurry result.
_IMAGE_SIZE_RE = re.compile(r"/s-l\d+\.jpg$")


def _hd_image(url: str) -> str:
    return _IMAGE_SIZE_RE.sub("/s-l1600.jpg", url)

# Curated fashion search terms -> our category slug. eBay's Browse API
# doesn't reliably return brand/gender/color on item_summary rows (only on
# the per-item detail call, which would be an expensive N+1) so those stay
# unset rather than guessed — the term only ever drives categorization.
_SEARCH_TERMS: list[tuple[str, str]] = [
    ("dress", "dresses"),
    ("jacket", "jackets"),
    ("jeans", "denim"),
    ("sneakers", "sneakers"),
    ("t-shirt", "tops"),
    ("handbag", "bags"),
    ("sunglasses", "accessories"),
    ("watch", "watches"),
    ("boots", "boots"),
    ("hat", "hats"),
    ("coat", "coats"),
    ("suit", "formalwear"),
]


class EbayProductProvider(ProductProvider):
    slug = "ebay"
    display_name = "eBay"

    def __init__(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        campaign_id: str | None,
        marketplace_id: str = "EBAY_US",
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._campaign_id = campaign_id
        self._marketplace_id = marketplace_id
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        if not (self._client_id and self._client_secret):
            raise RetailerNotConfiguredError(
                "eBay API credentials not set (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET)"
            )

        products: list[RawProduct] = []
        seen_ids: set[str] = set()
        last_error: Exception | None = None
        any_term_succeeded = False

        async with httpx.AsyncClient(timeout=20) as client:
            token = await self._get_token(client)
            headers = {
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
            }

            per_term = max(1, limit // len(_SEARCH_TERMS) + 1)
            for term, category_slug in _SEARCH_TERMS:
                if len(products) >= limit:
                    break
                # One bad search term must not discard every term already
                # fetched — skip it and keep going, same resilience
                # guarantee sync_all_retailers gives at the retailer level.
                # But if *every* term fails, that's a systemic problem —
                # raise rather than silently reporting zero products as if
                # that were a normal empty result.
                try:
                    term_results = await self._search(client, headers, term, category_slug, per_term)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ebay_search_term_failed", term=term, error=str(exc))
                    last_error = exc
                    continue
                any_term_succeeded = True
                for raw in term_results:
                    if raw.retailer_product_id in seen_ids:
                        continue
                    seen_ids.add(raw.retailer_product_id)
                    products.append(raw)
                    if len(products) >= limit:
                        break

        if not any_term_succeeded and last_error is not None:
            raise last_error

        return products[:limit]

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        if not (self._client_id and self._client_secret):
            raise RetailerNotConfiguredError(
                "eBay API credentials not set (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET)"
            )
        async with httpx.AsyncClient(timeout=20) as client:
            token = await self._get_token(client)
            headers = {
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
            }
            return await self._search(client, headers, query, category_slug="search", limit=limit)

    async def fetch_by_id(self, retailer_product_id: str) -> RawProduct | None:
        """The listing itself, by the id the search returned. A click
        shouldn't need the retailer to rank the item back onto page one."""
        if not (self._client_id and self._client_secret):
            raise RetailerNotConfiguredError(
                "eBay API credentials not set (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET)"
            )
        async with httpx.AsyncClient(timeout=20) as client:
            token = await self._get_token(client)
            resp = await client.get(
                f"{_ITEM_URL}/{retailer_product_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
                },
            )
        if resp.status_code == 404:
            return None  # genuinely gone: ended, withdrawn, or never existed
        if resp.status_code >= 400:
            raise RuntimeError(f"eBay item lookup failed for {retailer_product_id}: {resp.status_code} {resp.text[:200]}")
        item = resp.json()
        return self._to_raw_product(item, "search") if self._is_usable(item) else None

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token

        resp = await client.post(
            _TOKEN_URL,
            auth=(self._client_id, self._client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": _OAUTH_SCOPE},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"eBay OAuth token request failed: {resp.status_code} {resp.text}")

        data = resp.json()
        self._token = data["access_token"]
        # refresh a little early rather than racing the real expiry
        self._token_expires_at = time.monotonic() + max(60, int(data.get("expires_in", 7200)) - 60)
        return self._token

    async def _search(
        self, client: httpx.AsyncClient, headers: dict, query: str, category_slug: str, limit: int
    ) -> list[RawProduct]:
        resp = await client.get(
            _SEARCH_URL,
            headers=headers,
            params={"q": query, "limit": min(limit, _PAGE_SIZE)},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"eBay Browse search failed for {query!r}: {resp.status_code} {resp.text}")

        items = resp.json().get("itemSummaries") or []
        return [self._to_raw_product(item, category_slug) for item in items if self._is_usable(item)]

    @staticmethod
    def _is_usable(item: dict) -> bool:
        return bool(item.get("itemId") and item.get("title") and item.get("price") and item.get("itemWebUrl"))

    @staticmethod
    def _to_raw_product(item: dict, category_slug: str) -> RawProduct:
        price = item["price"]
        images = [_hd_image(item["image"]["imageUrl"])] if item.get("image", {}).get("imageUrl") else []
        images += [_hd_image(img["imageUrl"]) for img in item.get("additionalImages", []) if img.get("imageUrl")]

        condition = (item.get("condition") or "").upper()
        availability = "out_of_stock" if condition == "SOLD" else "in_stock"

        return RawProduct(
            retailer_product_id=item["itemId"],
            name=item["title"],
            price_cents=round(float(price["value"]) * 100),
            currency=price.get("currency", "USD").lower(),
            product_url=item["itemWebUrl"],
            images=images,
            category_slug=category_slug,
            subcategory=(item.get("categories") or [{}])[0].get("categoryName"),
            availability=availability,
        )

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        # eBay Partner Network campid — falls back to the generic tracking
        # tag until EBAY_CAMPAIGN_ID is set (real EPN campaign, separate
        # from Browse API credentials).
        sep = "&" if "?" in product_url else "?"
        campid = self._campaign_id or tracking_tag
        return f"{product_url}{sep}campid={campid}"
