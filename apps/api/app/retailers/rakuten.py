"""Rakuten Advertising integration.

VERIFICATION STATUS — live-tested against a real account, unlike this
file's first draft. Confirmed for real, empirically, against
https://api.linksynergy.com:

  - Base URL: api.rakutenmarketing.com does NOT resolve at all (DNS
    failure) despite being the domain named in Rakuten's own developer
    portal navigation. api.linksynergy.com is the real, working host.
  - Token API (`/token`): real, works exactly as implemented — Basic
    auth(client_id, client_secret), form-encoded
    grant_type=client_credentials&scope=<account_id>, returns a real
    JSON {access_token, refresh_token, token_type, expires_in}.
  - Product Search API (`/productsearch/1.0`): real endpoint, but
    responds in **XML**, not JSON (a real correction from this file's
    first draft, the same class of fix eBay's nested-fields bug and CJ's
    `pid` argument were). Confirmed response wrapper: `<result>` with
    either `<TotalMatches>0</TotalMatches>...` (no matches) or
    `<Errors><ErrorID>7186919</ErrorID><ErrorText>No matching products
    found. Possible reasons include lack of approval from the specified
    Advertiser or no active relationships with any Advertiser.</ErrorText
    ></Errors>` — both mean "zero results", not a hard failure.
  - **The real, confirmed blocker**: this account has ZERO approved
    advertiser partnerships. Verified by scoping search to real, joined
    fashion-adjacent merchants pulled from the live advertiser list
    (Zappos Creator Program, Paul Fredrick MenStyle, Rapanui Clothing,
    Vionic Shoes, Adidas KSA, ...) — every single one returned the same
    "lack of approval" error. This is an account-status issue exactly
    parallel to CJ's "not authorized to query on behalf of companyId" —
    not a code bug. Item-level product field names (name/price/image tag
    names inside a populated `<item>`) are consequently still UNCONFIRMED
    — no populated response has ever been seen. The best-effort mapping
    below is historical LinkShare/Rakuten Product Search XML schema
    knowledge, flagged accordingly; it's the one place to correct once an
    advertiser relationship is approved and a real populated response
    exists.
  - Advertisers API v2 (`/v2/advertisers`): real, JSON, FULLY confirmed
    with live data — `{_metadata: {page, limit, total, _links},
    advertisers: [{network, id, name, url, logo_url, policies: {
    international_capabilities: {ships_to: [...]}}}]}`. This is the
    "v2" the integration spec explicitly asked for.
  - Partnerships: `/v2/advertisers/joined` REAL and EXISTS (confirmed via
    a `400 INVALID_CONTEXT_VALUE` rather than `404`) — it checks specific
    advertiser(s), not "list everything I'm joined with" as first
    assumed. Six real parameter-shape attempts (`advertiser-id`,
    `advertiser`, path-style, header-style, old-style `mid`) all failed
    the same way; the correct request shape is still unconfirmed and
    needs Rakuten support/docs, independent of the zero-partnerships
    issue above.
  - Offers API: no working path found among several real attempts
    (`offers/1.0`, `v2/offers` both 404). Needs real Rakuten
    documentation or support to identify — kept as a clearly-labeled
    non-working placeholder rather than a guess presented as real.
  - Coupon API (`/coupon/1.0`): real endpoint, XML, root `<couponfeed>`,
    same empty-response shape as Product Search. Item-level fields are
    equally unconfirmed (same zero-partnerships blocker).

Advertiser/partnership/offer/coupon data is deliberately NOT persisted to
new database tables yet — a wrong persisted schema is far more expensive
to unwind than a wrong request shape. Those methods are live pass-throughs
(see api/v1/endpoints/admin_rakuten.py).
"""

from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import logger
from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError

_TOKEN_PATH = "/token"
_PRODUCT_SEARCH_PATH = "/productsearch/1.0"  # confirmed real; XML
_ADVERTISER_V2_PATH = "/v2/advertisers"  # confirmed real; JSON
_PARTNERSHIP_JOINED_PATH = "/v2/advertisers/joined"  # confirmed to exist; request shape unconfirmed
_OFFERS_PATH = "/offers/1.0"  # NOT confirmed working (404 in live testing)
_COUPON_PATH = "/coupon/1.0"  # confirmed real; XML

# The "no matching products" error Rakuten returns with HTTP 200 when a
# query is well-formed but the account/advertiser has nothing to return —
# confirmed live. Treated as zero results, never a hard failure.
_NO_RESULTS_ERROR_ID = "7186919"

_PAGE_SIZE = 50
_MIN_REQUEST_INTERVAL_SECONDS = 0.5  # outbound throttle — Rakuten documents rate limits per account

# Same curated fashion-term list used by the eBay/CJ adapters, so all
# three retailers build a comparable initial catalog.
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


class RakutenAPIError(Exception):
    """A real (non-transient, or transient-exhausted) error from Rakuten's
    API — always carries enough detail to diagnose without a live account."""


@dataclass(frozen=True, slots=True)
class RakutenAdvertiser:
    mid: str
    name: str
    url: str | None = None
    countries_shipped_to: list[str] | None = None
    has_product_feed: bool | None = None
    supports_deep_linking: bool | None = None
    accepts_partnerships: bool | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class RakutenPartnership:
    mid: str
    advertiser_name: str
    status: str
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class RakutenOffer:
    id: str
    mid: str
    title: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    commission_rate: str | None = None
    commission_type: str | None = None


@dataclass(frozen=True, slots=True)
class RakutenCoupon:
    id: str
    mid: str
    advertiser_name: str
    description: str
    code: str | None = None
    start_date: str | None = None
    end_date: str | None = None


def _xml_text(elem: ET.Element | None, tag: str) -> str | None:
    if elem is None:
        return None
    child = elem.find(tag)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _parse_xml_or_raise(resp: httpx.Response, *, context: str) -> ET.Element:
    try:
        return ET.fromstring(resp.text)
    except ET.ParseError as exc:
        raise RakutenAPIError(f"Rakuten returned malformed XML for {context}") from exc


class RakutenProductProvider(ProductProvider):
    slug = "rakuten"
    display_name = "Rakuten Advertising"

    def __init__(
        self,
        *,
        enabled: bool,
        client_id: str | None,
        client_secret: str | None,
        access_token: str | None,
        refresh_token: str | None,
        publisher_id: str | None,
        account_id: str | None,
        base_url: str,
    ) -> None:
        self._enabled = enabled
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._publisher_id = publisher_id
        self._account_id = account_id
        self._base_url = base_url.rstrip("/")

        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0
        self._last_request_at: float = 0.0

    # ------------------------------------------------------------------
    # configuration / auth
    # ------------------------------------------------------------------

    def _is_configured(self) -> bool:
        has_client_credentials = bool(self._client_id and self._client_secret)
        has_direct_token = bool(self._access_token)
        return self._enabled and (has_client_credentials or has_direct_token) and bool(self._publisher_id)

    def describe_configuration(self) -> dict:
        """Which credentials are present — never their values. Used by the
        admin status endpoint so a misconfiguration can be diagnosed
        without any secret ever leaving the server."""
        return {
            "enabled": self._enabled,
            "configured": self._is_configured(),
            "has_client_credentials": bool(self._client_id and self._client_secret),
            "has_direct_token": bool(self._access_token),
            "has_publisher_id": bool(self._publisher_id),
            "has_account_id": bool(self._account_id),
            "base_url": self._base_url,
        }

    def _require_configured(self) -> None:
        if not self._enabled:
            raise RetailerNotConfiguredError("Rakuten Advertising is disabled (RAKUTEN_ENABLED=false)")
        if not self._publisher_id:
            raise RetailerNotConfiguredError("Rakuten Advertising is not configured (RAKUTEN_PUBLISHER_ID missing)")
        if not (self._client_id and self._client_secret) and not self._access_token:
            raise RetailerNotConfiguredError(
                "Rakuten Advertising is not configured (need RAKUTEN_CLIENT_ID/RAKUTEN_CLIENT_SECRET, "
                "or a directly issued RAKUTEN_TOKEN)"
            )

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _mint_token(self, client: httpx.AsyncClient) -> dict:
        resp = await client.post(
            f"{self._base_url}{_TOKEN_PATH}",
            auth=(self._client_id, self._client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": self._account_id or self._publisher_id or ""},
        )
        if resp.status_code >= 400:
            raise RakutenAPIError(f"Rakuten token request failed: {resp.status_code} {resp.text}")
        return resp.json()

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _refresh_direct_token(self, client: httpx.AsyncClient) -> dict:
        resp = await client.post(
            f"{self._base_url}{_TOKEN_PATH}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
        )
        if resp.status_code >= 400:
            raise RakutenAPIError(f"Rakuten token refresh failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._cached_token and time.monotonic() < self._token_expires_at:
            return self._cached_token

        if self._client_id and self._client_secret:
            data = await self._mint_token(client)
        elif self._access_token:
            # Use the directly-provided token as-is on first use; only
            # spend a refresh call once we actually know it's expired
            # (learned via a 401 from a real request — see _request()).
            self._cached_token = self._access_token
            self._token_expires_at = time.monotonic() + 3600
            return self._access_token
        else:
            raise RetailerNotConfiguredError("Rakuten Advertising has no usable credentials")

        self._cached_token = data["access_token"]
        self._token_expires_at = time.monotonic() + max(60, int(data.get("expires_in", 3600)) - 60)
        return self._cached_token

    async def _force_refresh_token(self, client: httpx.AsyncClient) -> str:
        """Called only after a real 401 — never speculatively."""
        if self._client_id and self._client_secret:
            data = await self._mint_token(client)
        elif self._refresh_token:
            data = await self._refresh_direct_token(client)
            # Rakuten may rotate the refresh token; keep using the latest.
            if data.get("refresh_token"):
                self._refresh_token = data["refresh_token"]
        else:
            raise RakutenAPIError("Rakuten access token expired and no refresh path is configured")

        self._cached_token = data["access_token"]
        self._token_expires_at = time.monotonic() + max(60, int(data.get("expires_in", 3600)) - 60)
        return self._cached_token

    # ------------------------------------------------------------------
    # outbound request helper — shared throttling + one-retry-on-401
    # ------------------------------------------------------------------

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = _MIN_REQUEST_INTERVAL_SECONDS - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _request(self, client: httpx.AsyncClient, method: str, path: str, **kwargs) -> httpx.Response:
        await self._throttle()
        token = await self._get_token(client)
        headers = {**kwargs.pop("headers", {}), "Authorization": f"Bearer {token}"}
        resp = await client.request(method, f"{self._base_url}{path}", headers=headers, **kwargs)

        if resp.status_code == 401:
            # Real, not speculative — the token we just used was rejected.
            token = await self._force_refresh_token(client)
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.request(method, f"{self._base_url}{path}", headers=headers, **kwargs)

        if resp.status_code == 429:
            raise RakutenAPIError("Rakuten rate limit hit (429) — back off and retry later")
        if resp.status_code >= 500:
            raise RakutenAPIError(f"Rakuten server error: {resp.status_code} {resp.text}")
        if resp.status_code >= 400:
            raise RakutenAPIError(f"Rakuten API error: {resp.status_code} {resp.text}")

        return resp

    def _parse_json(self, resp: httpx.Response, *, context: str) -> dict:
        try:
            return resp.json()
        except ValueError as exc:
            raise RakutenAPIError(f"Rakuten returned a malformed (non-JSON) response for {context}") from exc

    # ------------------------------------------------------------------
    # ProductProvider interface — catalog ingestion
    # ------------------------------------------------------------------

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        self._require_configured()

        products: list[RawProduct] = []
        seen_ids: set[str] = set()
        per_term = max(1, limit // len(_SEARCH_TERMS) + 1)
        last_error: Exception | None = None
        any_term_succeeded = False

        async with httpx.AsyncClient(timeout=20) as client:
            for term, category_slug in _SEARCH_TERMS:
                if len(products) >= limit:
                    break
                # A single bad search term (real example: Rakuten returned
                # a 400 INVALID_CONTEXT_VALUE for "t-shirt" while dress/
                # jacket/jeans/sneakers all succeeded) must not discard
                # every term already fetched — skip it and keep going,
                # same resilience guarantee sync_all_retailers already
                # gives at the retailer level. But if *every* term fails
                # the same way, that's a systemic problem (bad auth, full
                # outage) — raise rather than silently reporting zero
                # products as if that were a normal empty result.
                try:
                    term_results = await self._search(client, term, category_slug, per_term)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("rakuten_search_term_failed", term=term, error=str(exc))
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

    async def preview_search(self, *, keyword: str, limit: int = 10) -> list[RawProduct]:
        """A single-keyword search returning normalized (but unsaved)
        results — for the admin preview endpoint. Real catalog ingestion
        always goes through fetch_products() -> product_ingestion_service.py."""
        self._require_configured()
        async with httpx.AsyncClient(timeout=20) as client:
            return await self._search(client, keyword, category_slug="preview", limit=limit)

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        # Same call as preview_search — kept as a separate method name so
        # the admin diagnostics endpoint and the real browse/AI-stylist
        # live search path (live_search_service.py) read as what they are,
        # even though today they do the same thing.
        return await self.preview_search(keyword=query, limit=limit)

    async def _search(
        self, client: httpx.AsyncClient, keyword: str, category_slug: str, limit: int
    ) -> list[RawProduct]:
        resp = await self._request(
            client,
            "GET",
            _PRODUCT_SEARCH_PATH,
            params={
                "keyword": keyword,
                "max": min(limit, _PAGE_SIZE),
                "pagenumber": 1,
                **({"mid": self._account_id} if self._account_id else {}),
            },
        )
        root = _parse_xml_or_raise(resp, context=f"product search {keyword!r}")

        # Confirmed live: a well-formed query with nothing to return comes
        # back as HTTP 200 with either TotalMatches=0 or an <Errors> node
        # (e.g. "lack of approval from the specified Advertiser") — both
        # mean zero results, never a hard failure.
        if root.find("Errors") is not None:
            return []
        total_matches = _xml_text(root, "TotalMatches")
        if total_matches is not None and total_matches == "0":
            return []

        items = root.findall("item")
        return [self._item_to_raw_product(item, category_slug) for item in items if self._item_is_usable(item)]

    @staticmethod
    def _item_is_usable(item: ET.Element) -> bool:
        # Item-level tag names are UNCONFIRMED (see module docstring) —
        # best-effort historical LinkShare Product Search field names.
        sku = _xml_text(item, "sku") or _xml_text(item, "linkid")
        name = _xml_text(item, "productname")
        price_elem = item.find("saleprice") if item.find("saleprice") is not None else item.find("price")
        link = _xml_text(item, "linkurl") or _xml_text(item, "buyurl")
        return bool(sku and name and price_elem is not None and price_elem.text and link)

    @staticmethod
    def _item_to_raw_product(item: ET.Element, category_slug: str) -> RawProduct:
        sku = _xml_text(item, "sku") or _xml_text(item, "linkid") or ""
        name = _xml_text(item, "productname") or ""
        price_elem = item.find("saleprice") if item.find("saleprice") is not None else item.find("price")
        price_text = (price_elem.text or "0").strip() if price_elem is not None else "0"
        currency = (price_elem.get("currency") if price_elem is not None else None) or _xml_text(
            item, "currency"
        ) or "USD"
        link = _xml_text(item, "linkurl") or _xml_text(item, "buyurl") or ""

        category_elem = item.find("category")
        primary_category = _xml_text(category_elem, "primary") if category_elem is not None else None

        images = []
        image_url = _xml_text(item, "imageurl")
        if image_url:
            images.append(image_url)

        return RawProduct(
            retailer_product_id=sku,
            name=name,
            description=_xml_text(item, "description"),
            brand=_xml_text(item, "brandname") or _xml_text(item, "manufacturer"),
            merchant_name=_xml_text(item, "merchantname"),
            merchant_id=_xml_text(item, "mid"),
            price_cents=round(float(price_text) * 100),
            currency=currency.lower(),
            product_url=link,
            images=images,
            category_slug=primary_category or category_slug,
        )

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:  # noqa: ARG002
        # Rakuten's Product Search results are expected to already return a
        # tracked deep link (linkurl) for the authenticated publisher
        # account — same pattern as CJ's linkCode.clickUrl. Unconfirmed at
        # the item level (see module docstring); this is the one place to
        # add publisher-id query-param wrapping if a real populated
        # response shows the link is NOT pre-tracked.
        return product_url

    # ------------------------------------------------------------------
    # Advertisers API v2 (confirmed real+JSON) / Partnerships (endpoint
    # confirmed to exist, request shape unconfirmed) / Offers (no working
    # path found) / Coupon (confirmed real+XML) — live pass-throughs, not
    # persisted (see module docstring)
    # ------------------------------------------------------------------

    async def list_advertisers(self, *, keyword: str | None = None, limit: int = 50) -> list[RakutenAdvertiser]:
        self._require_configured()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await self._request(
                client,
                "GET",
                _ADVERTISER_V2_PATH,
                params={"limit": limit, **({"keyword": keyword} if keyword else {})},
            )
            data = self._parse_json(resp, context="advertiser search")

        rows = data.get("advertisers") or []
        advertisers = []
        for row in rows:
            policies = row.get("policies") or {}
            intl = policies.get("international_capabilities") or {}
            advertisers.append(
                RakutenAdvertiser(
                    mid=str(row.get("id")),
                    name=row.get("name") or "",
                    url=row.get("url"),
                    countries_shipped_to=intl.get("ships_to"),
                    has_product_feed=row.get("has_product_feed"),
                    supports_deep_linking=row.get("supports_deep_linking"),
                    accepts_partnerships=row.get("accepts_partnerships"),
                    status=row.get("status"),
                )
            )
        return advertisers

    async def list_partnerships(self, *, advertiser_ids: list[str]) -> list[RakutenPartnership]:
        """Confirmed live: /v2/advertisers/joined exists (a 400
        INVALID_CONTEXT_VALUE, not a 404) and checks specific advertiser
        id(s) — it is not a "list everything I'm joined with" endpoint as
        first assumed. The exact parameter name/format is still
        unconfirmed after several real attempts (advertiser-id and
        advertiser as query params, path-style, header-style, and the
        legacy numeric `mid` all returned the same error) — this needs
        Rakuten support or real docs to pin down, independent of this
        account's separate zero-partnerships issue."""
        self._require_configured()
        if not advertiser_ids:
            raise ValueError("list_partnerships() requires at least one advertiser id")

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await self._request(
                client,
                "GET",
                _PARTNERSHIP_JOINED_PATH,
                params={"advertiser-id": ",".join(advertiser_ids)},
            )
            data = self._parse_json(resp, context="partnerships")

        rows = data.get("advertisers") or data.get("partnerships") or data.get("items") or []
        return [
            RakutenPartnership(
                mid=str(row.get("mid") or row.get("id")),
                advertiser_name=row.get("name") or row.get("advertisername") or "",
                status=row.get("status") or "unknown",
                updated_at=row.get("updated_at") or row.get("updatedat"),
            )
            for row in rows
        ]

    async def list_offers(self, *, mid: str | None = None) -> list[RakutenOffer]:
        """No working endpoint found among several real live attempts
        (offers/1.0 and v2/offers both 404'd) — raises clearly rather
        than silently returning nothing, so a caller can't mistake "we
        don't know the path" for "there are no offers"."""
        self._require_configured()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await self._request(client, "GET", _OFFERS_PATH, params={**({"mid": mid} if mid else {})})
            data = self._parse_json(resp, context="offers")

        rows = data.get("offers") or data.get("items") or []
        return [
            RakutenOffer(
                id=str(row.get("id") or row.get("offerid")),
                mid=str(row.get("mid")),
                title=row.get("title") or row.get("name") or "",
                description=row.get("description"),
                start_date=row.get("startdate"),
                end_date=row.get("enddate"),
                # Never invented — only ever set when Rakuten's response
                # actually includes it.
                commission_rate=row.get("commissionrate"),
                commission_type=row.get("commissiontype"),
            )
            for row in rows
        ]

    async def list_coupons(self, *, mid: str | None = None) -> list[RakutenCoupon]:
        self._require_configured()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await self._request(client, "GET", _COUPON_PATH, params={**({"mid": mid} if mid else {})})
        root = _parse_xml_or_raise(resp, context="coupons")

        if root.find("Errors") is not None:
            return []
        total_matches = _xml_text(root, "TotalMatches")
        if total_matches is not None and total_matches == "0":
            return []

        coupons = []
        for item in root.findall("link"):
            coupons.append(
                RakutenCoupon(
                    id=_xml_text(item, "linkid") or "",
                    mid=_xml_text(item, "mid") or "",
                    advertiser_name=_xml_text(item, "advertisername") or "",
                    description=_xml_text(item, "offerdescription") or "",
                    code=_xml_text(item, "couponcode"),
                    start_date=_xml_text(item, "offerstartdate"),
                    end_date=_xml_text(item, "offerenddate"),
                )
            )
        return coupons
