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

import time

import httpx

from app.core.logging import logger
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError

_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
_OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"
_PAGE_SIZE = 50

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
        images = [item["image"]["imageUrl"]] if item.get("image", {}).get("imageUrl") else []
        images += [img["imageUrl"] for img in item.get("additionalImages", []) if img.get("imageUrl")]

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
