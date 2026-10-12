"""Company stores: plan state, limits, search, and the feed import."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import and_, case, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.store import Store, StorePlan, StoreProduct
from app.services.admitad_feeds import parse_price
from app.services.safe_fetch import UnsafeURLError, check_public_url, fetch_limited

FEED_MAX_BYTES = 20 * 1024 * 1024
MAX_IMAGES = 6
GENDERS = {"women", "men", "unisex", "girls", "boys"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def plan_active(store: Store) -> bool:
    expires = _aware(store.plan_expires_at)
    return bool(store.plan_code) and expires is not None and expires > utcnow()


def is_live(store: Store) -> bool:
    """Shoppers see a store's products only while it is approved AND its plan is paid."""
    return store.status == "approved" and plan_active(store)


def image_url(entry: str) -> str:
    """An uploaded photo (a storage key) as its public web address; a feed photo as it is."""
    if entry.startswith("stores/"):
        base = get_settings().PUBLIC_API_BASE_URL.rstrip("/")
        return f"{base}/api/v1/stores/media/{entry}"
    return entry


async def unique_slug(db: AsyncSession, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:120] or "store"
    slug, n = base, 1
    while await db.scalar(select(Store.id).where(Store.slug == slug)):
        n += 1
        slug = f"{base}-{n}"
    return slug


async def active_product_count(db: AsyncSession, store_id: str) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(StoreProduct).where(
                StoreProduct.store_id == store_id, StoreProduct.is_active.is_(True)
            )
        )
        or 0
    )


def activate_plan(store: Store, plan: StorePlan) -> None:
    """A paid 30-day pass: added to whatever time is left, so renewing early
    loses nothing; the plan (and its product limit) becomes the one bought."""
    now = utcnow()
    start = max(now, _aware(store.plan_expires_at) or now)
    store.plan_code = plan.code
    store.plan_product_limit = plan.product_limit
    store.plan_expires_at = start + timedelta(days=plan.duration_days)


# --------------------------------------------------------------------- search

_IGNORED = {"women", "womens", "woman", "men", "mens", "man", "for", "and", "with", "the", "ladies", "girls", "boys", "unisex"}


async def search_store_products(
    db: AsyncSession, query: str, limit: int, country: str | None
) -> list[tuple[StoreProduct, Store]]:
    """Live stores' products whose name has every query word (leading words
    dropped until something matches), the shopper's own country first."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 3 and w not in _IGNORED]
    now = utcnow()
    live = and_(
        Store.status == "approved",
        Store.plan_code.is_not(None),
        Store.plan_expires_at > now,
        StoreProduct.is_active.is_(True),
    )
    local_first = case((Store.country == (country or ""), 0), else_=1)
    for start in range(len(words)):
        matches = [StoreProduct.name.ilike(f"%{w}%") for w in words[start:]]
        rows = (
            await db.execute(
                select(StoreProduct, Store)
                .join(Store, Store.id == StoreProduct.store_id)
                .where(live, *matches)
                .order_by(local_first, StoreProduct.updated_at.desc())
                .limit(limit)
            )
        ).all()
        if rows:
            return [(p, s) for p, s in rows]
    return []


# ----------------------------------------------------------------- feed import


def _first(row: dict, *keys: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for key in keys:
        value = lowered.get(key)
        if isinstance(value, list):
            value = ",".join(str(v) for v in value if v)
        if isinstance(value, dict):
            value = value.get("src") or value.get("url") or ""
        if value not in (None, ""):
            return str(value).strip()
    return ""


def parse_feed(data: bytes) -> list[dict]:
    """Rows of a CSV (comma, semicolon or tab) or JSON feed: a list of products,
    or an object with them under "products" / "items" / "data"."""
    text = data.decode("utf-8-sig", errors="replace").strip()
    if text.startswith(("[", "{")):
        body = json.loads(text)
        if isinstance(body, dict):
            body = next((body[k] for k in ("products", "items", "data") if isinstance(body.get(k), list)), [])
        return [r for r in body if isinstance(r, dict)]
    header = text.splitlines()[0] if text else ""
    delimiter = "\t" if "\t" in header else (";" if header.count(";") > header.count(",") else ",")
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def normalize_feed_row(row: dict, host_ok) -> dict | None:  # noqa: ANN001
    """One feed row as store-product fields, or None when it lacks a name,
    price, product link or a usable public photo. Shopify/WooCommerce/Google
    column names are all understood."""
    name = _first(row, "name", "title", "product_name")
    url = _first(row, "url", "link", "product_url", "permalink")
    offer = _first(row, "id", "sku", "product_id", "offer_id", "handle") or url
    price = parse_price(_first(row, "sale_price", "price", "regular_price", "variant price"))
    raw_images = _first(row, "images", "image", "image_url", "image_link", "picture", "image src", "additional_image_link")
    images = [i.strip() for i in re.split(r"[,\s|]+", raw_images) if i.strip().startswith(("http://", "https://"))]
    images = [i for i in images if host_ok(i)][:MAX_IMAGES]
    if not (name and url.startswith(("http://", "https://")) and price and images):
        return None
    currency = _first(row, "currency", "currencyid", "currency_code")
    if not currency:
        found = re.search(r"\b([A-Za-z]{3})\b", _first(row, "price"))
        currency = found.group(1) if found else "usd"
    gender = _first(row, "gender").lower()
    available = _first(row, "available", "availability", "in_stock").lower()
    return {
        "external_id": offer[:128],
        "name": name[:512],
        "description": _first(row, "description", "body (html)", "short_description")[:4000] or None,
        "price_cents": price,
        "currency": currency.lower()[:8],
        "images": images,
        "product_url": url[:2048],
        "category": _first(row, "category", "product_type", "type", "category_name")[:120] or None,
        "gender": gender if gender in GENDERS else "unisex",
        "color": _first(row, "color", "colour")[:60] or None,
        "is_active": available not in ("false", "0", "no", "out of stock", "out_of_stock"),
    }


def _host_checker():  # noqa: ANN202
    """Checks each photo host once per import (one DNS lookup per host)."""
    seen: dict[str, bool] = {}

    def ok(url: str) -> bool:
        host = urlparse(url).hostname or ""
        if host not in seen:
            try:
                check_public_url(url)
                seen[host] = True
            except UnsafeURLError:
                seen[host] = False
        return seen[host]

    return ok


async def import_store_feed(db: AsyncSession, store: Store) -> str:
    """Replaces the store's feed products with what its feed link holds now,
    keeping typed-in products, within the plan's product limit. Returns a
    one-line result that the dashboard shows."""
    store.feed_last_run_at = utcnow()
    if not store.feed_url:
        store.feed_last_result = "No feed link set."
        await db.commit()
        return store.feed_last_result
    try:
        data = await asyncio.to_thread(fetch_limited, store.feed_url, max_bytes=FEED_MAX_BYTES)
        rows = await asyncio.to_thread(parse_feed, data)
    except UnsafeURLError as exc:
        store.feed_last_result = f"Feed link refused: {exc}."
        await db.commit()
        return store.feed_last_result
    except Exception as exc:  # noqa: BLE001 — shown to the company, nothing else breaks
        store.feed_last_result = f"Couldn't read the feed: {str(exc)[:160]}"
        await db.commit()
        return store.feed_last_result

    host_ok = _host_checker()
    items: dict[str, dict] = {}
    skipped = 0
    for row in rows:
        item = await asyncio.to_thread(normalize_feed_row, row, host_ok)
        if item is None:
            skipped += 1
            continue
        items.setdefault(item["external_id"], item)

    manual = int(
        await db.scalar(
            select(func.count()).select_from(StoreProduct).where(
                StoreProduct.store_id == store.id,
                StoreProduct.source == "manual",
                StoreProduct.is_active.is_(True),
            )
        )
        or 0
    )
    room = max(0, store.plan_product_limit - manual)
    kept = list(items.values())[:room]
    await db.execute(delete(StoreProduct).where(StoreProduct.store_id == store.id, StoreProduct.source == "feed"))
    if kept:
        await db.execute(
            insert(StoreProduct),
            [{"id": str(uuid.uuid4()), "store_id": store.id, "source": "feed", **item} for item in kept],
        )
    over = len(items) - len(kept)
    store.feed_last_result = (
        f"Imported {len(kept)} products"
        + (f"; {over} more didn't fit your plan's limit of {store.plan_product_limit}" if over else "")
        + (f"; {skipped} rows skipped (missing name, price, link or photo)" if skipped else "")
        + "."
    )
    await db.commit()
    return store.feed_last_result
