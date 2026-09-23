"""Amazon Product Advertising API (PA-API 5.0) adapter.

Amazon is the retailer shoppers name first, and its fashion catalogue is
enormous — but the API is the hardest to get into: PA-API access needs an
approved Associates account that has already made three qualifying sales
in 180 days. So this is written to be correct the day those keys exist,
and to say plainly that it isn't configured until then.

The call is SearchItems on the marketplace's host, signed with AWS
Signature V4 (service "ProductAdvertisingAPI"), the operation named both
in the path and in the X-Amz-Target header, and the body as JSON.
`Resources` has to list every field we want back — PA-API returns nothing
beyond ASIN unless it is asked for by name.

Not verified against the live API: no credentials exist to call it with.
The signing is tested against AWS's own worked example so it can't drift,
and the response mapping against the documented shape.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.logging import logger
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError

_SERVICE = "ProductAdvertisingAPI"
_TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
_PATH = "/paapi5/searchitems"
_MAX_ITEMS = 10  # PA-API's hard cap per SearchItems call

# Marketplaces we might serve, and where each one's API lives.
MARKETPLACES = {
    "www.amazon.com": ("webservices.amazon.com", "us-east-1"),
    "www.amazon.co.uk": ("webservices.amazon.co.uk", "eu-west-1"),
    "www.amazon.de": ("webservices.amazon.de", "eu-west-1"),
    "www.amazon.ae": ("webservices.amazon.ae", "eu-west-1"),
    "www.amazon.sa": ("webservices.amazon.sa", "eu-west-1"),
    "www.amazon.in": ("webservices.amazon.in", "eu-west-1"),
    "www.amazon.com.au": ("webservices.amazon.com.au", "us-west-2"),
    "www.amazon.ca": ("webservices.amazon.ca", "us-east-1"),
    "www.amazon.sg": ("webservices.amazon.sg", "us-west-2"),
}

# PA-API returns only the ASIN unless each field is named
_RESOURCES = [
    "ItemInfo.Title",
    "ItemInfo.ByLineInfo",
    "ItemInfo.Classifications",
    "ItemInfo.ProductInfo",
    "Images.Primary.Large",
    "Images.Variants.Large",
    "Offers.Listings.Price",
    "Offers.Listings.Availability.Message",
]

_SYNC_TERMS = (
    "women kurta set",
    "men kurta pajama",
    "embroidered maxi dress",
    "leather jacket men",
    "women heels",
    "analog watch men",
)


class AmazonProductProvider(ProductProvider):
    slug = "amazon"
    display_name = "Amazon"

    def __init__(
        self,
        *,
        access_key: str | None,
        secret_key: str | None,
        partner_tag: str | None,
        marketplace: str = "www.amazon.com",
    ) -> None:
        self._access_key = access_key
        self._secret_key = secret_key
        self._partner_tag = partner_tag
        self._marketplace = marketplace
        self._host, self._region = MARKETPLACES.get(marketplace, MARKETPLACES["www.amazon.com"])

    # --- signing --------------------------------------------------------

    def _require_credentials(self) -> None:
        if not (self._access_key and self._secret_key and self._partner_tag):
            raise RetailerNotConfiguredError(
                "Amazon PA-API credentials not set (AMAZON_ACCESS_KEY / "
                "AMAZON_SECRET_KEY / AMAZON_PARTNER_TAG). Note PA-API also "
                "requires an approved Associates account with 3 qualifying "
                "sales in the last 180 days."
            )

    def _headers(self, body: str, now: datetime) -> dict[str, str]:
        """AWS Signature V4. The signed headers are exactly the four below,
        in this order — PA-API rejects a signature computed over any other
        set."""
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        day = stamp[:8]
        signed_headers = "content-encoding;host;x-amz-date;x-amz-target"
        canonical_headers = (
            "content-encoding:amz-1.0\n"
            f"host:{self._host}\n"
            f"x-amz-date:{stamp}\n"
            f"x-amz-target:{_TARGET}\n"
        )
        canonical_request = "\n".join(
            [
                "POST",
                _PATH,
                "",
                canonical_headers,
                signed_headers,
                hashlib.sha256(body.encode()).hexdigest(),
            ]
        )
        scope = f"{day}/{self._region}/{_SERVICE}/aws4_request"
        to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                stamp,
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )

        def sign(key: bytes, message: str) -> bytes:
            return hmac.new(key, message.encode(), hashlib.sha256).digest()

        key = sign(sign(sign(sign(f"AWS4{self._secret_key}".encode(), day), self._region), _SERVICE), "aws4_request")
        signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
        return {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": self._host,
            "x-amz-date": stamp,
            "x-amz-target": _TARGET,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self._access_key}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        }

    # --- products -------------------------------------------------------

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        self._require_credentials()
        body = json.dumps(
            {
                "Keywords": query,
                "SearchIndex": "Fashion",
                "ItemCount": min(limit, _MAX_ITEMS),
                "PartnerTag": self._partner_tag,
                "PartnerType": "Associates",
                "Marketplace": self._marketplace,
                "Resources": _RESOURCES,
            }
        )
        headers = self._headers(body, datetime.now(timezone.utc))
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"https://{self._host}{_PATH}", content=body, headers=headers)
        if resp.status_code == 429:
            raise RuntimeError("Amazon PA-API rate limit reached (TooManyRequests)")
        if resp.status_code >= 400:
            # PA-API explains refusals in an Errors array; surface it rather
            # than a bare status, because "not yet 3 sales" arrives this way
            detail = _first_error(resp) or resp.text[:300]
            raise RuntimeError(f"Amazon SearchItems failed: {resp.status_code} {detail}")
        items = (resp.json().get("SearchResult") or {}).get("Items") or []
        return [p for p in (_product(item) for item in items) if p is not None][:limit]

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        self._require_credentials()
        products: list[RawProduct] = []
        seen: set[str] = set()
        for term in _SYNC_TERMS:
            if len(products) >= limit:
                break
            try:
                found = await self.search_live(query=term, limit=_MAX_ITEMS)
            except Exception as exc:  # noqa: BLE001 — one term must not kill the sync
                logger.warning("amazon_sync_term_failed", term=term, error=str(exc)[:200])
                continue
            for product in found:
                if product.retailer_product_id in seen:
                    continue
                seen.add(product.retailer_product_id)
                products.append(product)
        return products[:limit]

    @property
    def ready(self) -> str:
        """What this retailer is waiting for, in one line — the admin panel
        and the connection test both show it."""
        if not self._partner_tag:
            return "No Associate ID set (AMAZON_PARTNER_TAG)"
        if not (self._access_key and self._secret_key):
            return (
                f"Affiliate tracking ready as {self._partner_tag} on {self._marketplace}, "
                "but PA-API keys are missing (AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY) — "
                "Amazon issues them from Associates -> Tools -> Product Advertising API, "
                "and only to an account with 3 qualifying sales in the last 180 days."
            )
        return f"Ready: {self._partner_tag} on {self._marketplace}"

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        """An Associate ID only earns on the marketplace it belongs to: a
        co.uk tag on an amazon.com link tracks nothing. So the tag goes on
        links to our own marketplace, and any other Amazon domain is left
        exactly as it is rather than carrying a tag that pays nothing and
        looks like it does."""
        tag = self._partner_tag or tracking_tag
        if f"//{self._marketplace}/" not in product_url and not product_url.startswith(f"https://{self._marketplace}"):
            logger.info("amazon_affiliate_tag_skipped", reason="different marketplace", url=product_url[:120])
            return product_url
        if f"tag={tag}" in product_url:  # DetailPageURL already carries it
            return product_url
        sep = "&" if "?" in product_url else "?"
        return f"{product_url}{sep}tag={tag}"


def _first_error(resp: httpx.Response) -> str | None:
    try:
        errors = resp.json().get("Errors") or []
    except ValueError:
        return None
    if not errors:
        return None
    first = errors[0]
    return f"{first.get('Code')}: {first.get('Message')}"


def _cents(listing: dict) -> tuple[int, str] | None:
    price = (listing.get("Price") or {}) if listing else {}
    amount, currency = price.get("Amount"), price.get("Currency")
    if amount is None:
        return None
    try:
        return round(float(amount) * 100), str(currency or "usd").lower()
    except (TypeError, ValueError):
        return None


def _images(item: dict) -> list[str]:
    images = item.get("Images") or {}
    urls = [((images.get("Primary") or {}).get("Large") or {}).get("URL")]
    for variant in images.get("Variants") or []:
        urls.append(((variant or {}).get("Large") or {}).get("URL"))
    return list(dict.fromkeys(u for u in urls if isinstance(u, str) and u.startswith("http")))[:6]


def _text(node: Any) -> str | None:
    value = (node or {}).get("DisplayValue") if isinstance(node, dict) else None
    return str(value) if value is not None else None


def _product(item: dict) -> RawProduct | None:
    asin = str(item.get("ASIN") or "").strip()
    info = item.get("ItemInfo") or {}
    name = _text(info.get("Title"))
    images = _images(item)
    listings = ((item.get("Offers") or {}).get("Listings")) or []
    price = _cents(listings[0]) if listings else None
    url = item.get("DetailPageURL")
    # without a price or a picture it can't be shown, tried on, or bought
    if not (asin and name and images and price and url):
        return None
    cents, currency = price
    availability = (((listings[0].get("Availability") or {}).get("Message")) or "").lower()
    return RawProduct(
        retailer_product_id=asin,
        name=name[:300],
        price_cents=cents,
        currency=currency,
        product_url=str(url),
        images=images,
        brand=_text((info.get("ByLineInfo") or {}).get("Brand")),
        subcategory=_text((info.get("Classifications") or {}).get("ProductGroup")),
        availability="in_stock" if "in stock" in availability or not availability else "out_of_stock",
    )
