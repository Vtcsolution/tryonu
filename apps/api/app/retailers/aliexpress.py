"""AliExpress affiliate adapter — worldwide catalog, open affiliate program.

Why this one next: eBay is the only live retailer we have, and its stock
of the things our shoppers actually ask for (khussa, maang tikka, kurta,
lehenga) is thin and US-centric. AliExpress carries all of it, ships to
Pakistan and most of the world, and its affiliate programme (the "Portals"
/ Open Platform affiliate API) accepts new publishers without the prior
sales Amazon's PA-API demands.

The call is the Open Platform "system" gateway: one POST to
https://api-sg.aliexpress.com/sync with the method name, the app key, a
timestamp and an HMAC-SHA256 signature over every parameter sorted by
name. Products come back under
aliexpress_affiliate_product_query_response.resp_result.result.products.

The listing URL we keep is `promotion_link` when the API returns one:
that is the tracked link that earns the commission, and it already carries
our tracking id, so build_affiliate_url leaves it alone. Without a
tracking id the API only returns plain product URLs and nothing is earned
— hence ALIEXPRESS_TRACKING_ID is required, not optional.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.logging import logger
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError

_GATEWAY = "https://api-sg.aliexpress.com/sync"
_SEARCH_METHOD = "aliexpress.affiliate.product.query"
_PAGE_SIZE = 50  # the API's maximum per page

# what to pull for the bulk catalogue sync, mirroring the eBay adapter:
# one short search per thing our shoppers actually ask for
_SYNC_TERMS = (
    "pakistani shalwar kameez",
    "embroidered kurti women",
    "lehenga choli",
    "khussa shoes",
    "maang tikka",
    "kundan jewellery set",
    "men kurta pajama",
    "peshawari chappal",
)


class AliExpressProductProvider(ProductProvider):
    slug = "aliexpress"
    display_name = "AliExpress"

    def __init__(
        self,
        *,
        app_key: str | None,
        app_secret: str | None,
        tracking_id: str | None,
        ship_to_country: str = "PK",
        currency: str = "USD",
        language: str = "EN",
        base_url: str = _GATEWAY,
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._tracking_id = tracking_id
        self._ship_to = ship_to_country
        self._currency = currency
        self._language = language
        self._base_url = base_url

    # --- the gateway ----------------------------------------------------

    def _require_credentials(self) -> None:
        missing = [
            name
            for name, value in (
                ("ALIEXPRESS_APP_KEY (or ALI_EXPRESS_APP_KEY)", self._app_key),
                ("ALIEXPRESS_APP_SECRET (or ALI_EXPRESS_SECRET_API)", self._app_secret),
                ("ALIEXPRESS_TRACKING_ID (or ALI_EXPRESS_TRACKING_ID)", self._tracking_id),
            )
            if not value
        ]
        if missing:
            raise RetailerNotConfiguredError(
                "AliExpress affiliate API not set — missing " + ", ".join(missing)
            )

    def _sign(self, params: dict[str, str]) -> str:
        """HMAC-SHA256 over every parameter, sorted by name and
        concatenated as name+value with no separators — the Open Platform's
        scheme for sign_method=sha256. Uppercase hex, as it expects."""
        payload = "".join(f"{key}{params[key]}" for key in sorted(params))
        signed = hmac.new(self._app_secret.encode(), payload.encode(), hashlib.sha256)  # type: ignore[union-attr]
        return signed.hexdigest().upper()

    async def _call(self, client: httpx.AsyncClient, method: str, business: dict[str, Any]) -> dict:
        params = {
            "app_key": str(self._app_key),
            "method": method,
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
            "timestamp": str(int(time.time() * 1000)),
            **{k: str(v) for k, v in business.items() if v is not None},
        }
        params["sign"] = self._sign(params)
        resp = await client.post(self._base_url, data=params)
        if resp.status_code >= 400:
            raise RuntimeError(f"AliExpress {method} failed: {resp.status_code} {resp.text[:300]}")
        body = resp.json()
        # the gateway reports its own errors with HTTP 200
        if "error_response" in body:
            error = body["error_response"]
            raise RuntimeError(
                f"AliExpress {method} rejected: {error.get('code')} {error.get('msg')} "
                f"{error.get('sub_msg') or ''}".strip()
            )
        return body

    # --- products -------------------------------------------------------

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        self._require_credentials()
        async with httpx.AsyncClient(timeout=20) as client:
            body = await self._call(
                client,
                _SEARCH_METHOD,
                {
                    "keywords": query,
                    "page_no": 1,
                    "page_size": min(limit, _PAGE_SIZE),
                    "target_currency": self._currency,
                    "target_language": self._language,
                    "ship_to_country": self._ship_to,
                    "tracking_id": self._tracking_id,
                    "sort": "SALE_PRICE_ASC",
                },
            )
        return [p for p in (_product(row) for row in _rows(body)) if p is not None][:limit]

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        self._require_credentials()
        products: list[RawProduct] = []
        seen: set[str] = set()
        per_term = max(4, limit // len(_SYNC_TERMS))
        for term in _SYNC_TERMS:
            if len(products) >= limit:
                break
            try:
                found = await self.search_live(query=term, limit=per_term)
            except Exception as exc:  # noqa: BLE001 — one bad term must not kill the sync
                logger.warning("aliexpress_sync_term_failed", term=term, error=str(exc)[:200])
                continue
            for product in found:
                if product.retailer_product_id in seen:
                    continue
                seen.add(product.retailer_product_id)
                products.append(product)
        return products[:limit]

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        # a promotion_link is already the tracked link for our account —
        # appending anything to it would only risk breaking attribution
        if "s.click.aliexpress.com" in product_url or "aff_trace_key=" in product_url:
            return product_url
        sep = "&" if "?" in product_url else "?"
        return f"{product_url}{sep}aff_short_key={tracking_tag}"


def _rows(body: dict) -> list[dict]:
    result = (
        body.get("aliexpress_affiliate_product_query_response", {})
        .get("resp_result", {})
        .get("result", {})
    )
    products = (result.get("products") or {}).get("product")
    if isinstance(products, list):
        return products
    return [products] if isinstance(products, dict) else []


def _cents(value: Any) -> int | None:
    try:
        return round(float(value) * 100)
    except (TypeError, ValueError):
        return None


def _images(row: dict) -> list[str]:
    main = row.get("product_main_image_url")
    extra = (row.get("product_small_image_urls") or {}).get("string") or []
    if isinstance(extra, str):
        extra = [extra]
    urls = [u for u in [main, *extra] if isinstance(u, str) and u.startswith("http")]
    return list(dict.fromkeys(urls))[:6]


def _product(row: dict) -> RawProduct | None:
    product_id = str(row.get("product_id") or "").strip()
    name = (row.get("product_title") or "").strip()
    images = _images(row)
    # sale price first: it's what the shopper pays, and what our budget
    # filters compare against
    price = _cents(row.get("target_sale_price") or row.get("target_original_price"))
    url = row.get("promotion_link") or row.get("product_detail_url")
    if not (product_id and name and images and price and url):
        return None
    return RawProduct(
        retailer_product_id=product_id,
        name=name[:300],
        price_cents=price,
        currency=str(row.get("target_sale_price_currency") or "USD").lower(),
        product_url=str(url),
        images=images,
        brand=None,
        subcategory=row.get("second_level_category_name") or row.get("first_level_category_name"),
        description=None,
        rating=_rating(row.get("evaluate_rate")),
        rating_count=int(row.get("lastest_volume") or 0),
        merchant_name=row.get("shop_name"),
        merchant_id=str(row["shop_id"]) if row.get("shop_id") else None,
    )


def _rating(value: Any) -> float | None:
    """The API gives an evaluation rate as a percentage string ("94.2%");
    our products carry a 0-5 rating."""
    if not isinstance(value, str) or not value.endswith("%"):
        return None
    try:
        return round(float(value[:-1]) / 20, 2)
    except ValueError:
        return None
