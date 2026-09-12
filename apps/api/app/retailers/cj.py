"""CJ Affiliate (Commission Junction) GraphQL Product API — real product
search with ready-made affiliate tracking baked into each result, no
separate deep-link wrapping step needed.

Auth: `Authorization: Bearer <CJ_API_TOKEN>` (a CJ Personal Access Token —
CJ developer portal > Account > API Keys). Verified live against the real
endpoint at https://ads.api.cj.com/query, including a full schema
introspection of the `products` query and its `Product`/`LinkCode` return
shape — this isn't a guess at the request/response format.

`companyId` (CJ's own name for what we call CJ_WEBSITE_ID — your CJ
publisher/account id, in the CJ dashboard) is a required, non-nullable
argument on the `products` query per that introspection: there is no way
to fetch real products without it.
"""

from __future__ import annotations

import httpx

from app.retailers.base import ProductProvider, RawProduct
from app.retailers.errors import RetailerNotConfiguredError

_API_URL = "https://ads.api.cj.com/query"

_PRODUCTS_QUERY = """
query Products($companyId: ID!, $pid: ID!, $limit: Int, $keywords: [String!]) {
  products(companyId: $companyId, limit: $limit, keywords: $keywords) {
    resultList {
      id
      title
      description
      brand
      imageLink
      additionalImageLink
      link
      linkCode(pid: $pid) { clickUrl }
      price { amount currency }
    }
  }
}
"""

# CJ has no "browse everything" endpoint either — like eBay's Browse API,
# every call is a keyword search. Same curated fashion-term list, mapped
# to our category slugs.
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


class CJProductProvider(ProductProvider):
    slug = "cj"
    display_name = "CJ Affiliate"

    def __init__(self, *, api_token: str | None, company_id: str | None) -> None:
        self._api_token = api_token
        self._company_id = company_id

    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        if not (self._api_token and self._company_id):
            raise RetailerNotConfiguredError(
                "CJ Affiliate credentials not set (CJ_API_TOKEN / CJ_WEBSITE_ID)"
            )

        products: list[RawProduct] = []
        seen_ids: set[str] = set()
        per_term = max(1, limit // len(_SEARCH_TERMS) + 1)

        async with httpx.AsyncClient(timeout=20) as client:
            for term, category_slug in _SEARCH_TERMS:
                if len(products) >= limit:
                    break
                for raw in await self._search(client, term, category_slug, per_term):
                    if raw.retailer_product_id in seen_ids:
                        continue
                    seen_ids.add(raw.retailer_product_id)
                    products.append(raw)
                    if len(products) >= limit:
                        break

        return products[:limit]

    async def _search(
        self, client: httpx.AsyncClient, query: str, category_slug: str, limit: int
    ) -> list[RawProduct]:
        resp = await client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {self._api_token}", "Content-Type": "application/json"},
            json={
                "query": _PRODUCTS_QUERY,
                "variables": {
                    "companyId": self._company_id,
                    # CJ's Publisher ID (pid) for link generation — same as
                    # the account's own id for a standard single-website
                    # setup (confirmed via a live, schema-validating call);
                    # would need its own setting if a publisher ever runs
                    # multiple distinct website PIDs under one account.
                    "pid": self._company_id,
                    "limit": min(limit, 50),
                    "keywords": [query],
                },
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"CJ Affiliate search failed for {query!r}: {resp.status_code} {resp.text}")

        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(f"CJ Affiliate GraphQL error for {query!r}: {data['errors']}")

        items = ((data.get("data") or {}).get("products") or {}).get("resultList") or []
        return [self._to_raw_product(item, category_slug) for item in items if self._is_usable(item)]

    @staticmethod
    def _is_usable(item: dict) -> bool:
        link = ((item.get("linkCode") or {}).get("clickUrl")) or item.get("link")
        return bool(item.get("id") and item.get("title") and item.get("price") and link)

    @staticmethod
    def _to_raw_product(item: dict, category_slug: str) -> RawProduct:
        price = item["price"]
        link = ((item.get("linkCode") or {}).get("clickUrl")) or item["link"]
        images = [item["imageLink"]] if item.get("imageLink") else []
        images += [u for u in (item.get("additionalImageLink") or []) if u]

        return RawProduct(
            retailer_product_id=item["id"],
            name=item["title"],
            brand=item.get("brand"),
            description=item.get("description"),
            price_cents=round(float(price["amount"]) * 100),
            currency=(price.get("currency") or "USD").lower(),
            product_url=link,
            images=images,
            category_slug=category_slug,
        )

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:  # noqa: ARG002
        # CJ's own linkCode.clickUrl (used as product_url above) is
        # already a tracked affiliate link for this account — nothing to
        # append, unlike eBay's campid or Amazon's tag scheme.
        return product_url
