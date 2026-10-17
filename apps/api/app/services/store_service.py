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

from sqlalchemy import and_, case, delete, func, insert, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.store import Store, StorePlan, StoreProduct, StoreProductView
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


def activate_plan(store: Store, plan: StorePlan, *, free: bool = False) -> None:
    """A 30-day pass: added to whatever time is left, so renewing early
    loses nothing; the plan (and its product limit) becomes the one bought.
    `free`: given by an admin without payment."""
    now = utcnow()
    start = max(now, _aware(store.plan_expires_at) or now)
    store.plan_code = plan.code
    store.plan_product_limit = plan.product_limit
    store.plan_featured_limit = plan.featured_limit or 0
    # try-on credits add up: what's left carries over into the new period
    store.tryon_credits = (store.tryon_credits or 0) + (plan.tryon_credits or 0)
    store.plan_expires_at = start + timedelta(days=plan.duration_days)
    store.plan_free = free


def end_plan(store: Store) -> None:
    """The plan stops now; the store's products leave search until a new plan."""
    now = utcnow()
    if store.plan_expires_at is not None and _aware(store.plan_expires_at) > now:
        store.plan_expires_at = now


# --------------------------------------------------------------------- search

# What stores call an item in other languages (Spanish, French, Portuguese):
# a shopper asking for "sandals" finds a store's "Sandalias ..." too.
ITEM_WORDS: dict[str, tuple[str, ...]] = {
    "dress": ("vestido", "robe"),
    "earrings": ("pendientes", "aretes", "boucles", "brincos"),
    "necklace": ("collar", "colgante", "gargantilla", "collier", "colar"),
    "bracelet": ("pulsera", "brazalete", "bracelete"),
    "bangles": ("brazalete",),
    "ring": ("anillo", "bague", "anel"),
    "bag": ("bolso", "bolsa", "sac"),
    "handbag": ("bolso", "sac"),
    "sandals": ("sandalias", "sandales", "sandalia"),
    "shoes": ("zapatos", "chaussures", "sapatos"),
    "heels": ("tacones", "tacón", "tacon", "escarpins"),
    "boots": ("botas", "bottes", "botines"),
    "watch": ("reloj", "montre", "relógio"),
    "scarf": ("pañuelo", "bufanda", "foulard", "écharpe"),
    "skirt": ("falda", "jupe", "saia"),
    "blouse": ("blusa", "chemisier"),
    "shirt": ("camisa", "chemise"),
    "jacket": ("chaqueta", "veste", "jaqueta"),
    "trousers": ("pantalón", "pantalones", "pantalon", "calça"),
    "jeans": ("vaqueros",),
    "sunglasses": ("gafas de sol", "lunettes de soleil"),
}
_FOREIGN_TO_ENGLISH = {foreign: english for english, words in ITEM_WORDS.items() for foreign in words}


def english_item_words(name: str) -> list[str]:
    """English item words for the foreign ones in a product name that the name
    doesn't already say in English: "Sandalias Gel" -> ["Sandals"]."""
    low = name.lower()
    found: list[str] = []
    for foreign, english in _FOREIGN_TO_ENGLISH.items():
        if re.search(rf"(?<![a-zà-ÿ]){re.escape(foreign)}(?![a-zà-ÿ])", low) and not re.search(rf"\b{english}\b", low):
            if english.capitalize() not in found:
                found.append(english.capitalize())
    if "Watch" in found and "Bracelet" in found:
        found.remove("Bracelet")  # "reloj de pulsera" is a wristwatch, not a bracelet
    return found


def shown_name(name: str) -> str:
    """A product's name as shoppers see it in search: a foreign name gets the
    English word next to it ("Pendientes de plata · Earrings"), so everyone
    knows what it is and English searches and checks recognise it."""
    extra = english_item_words(name)
    return f"{name} · {', '.join(extra)}" if extra else name


def _word_condition(word: str):  # noqa: ANN202 - a SQL condition
    """The query word in a product's name or category, or a foreign word for it in its name."""
    options = [StoreProduct.name.ilike(f"%{word}%"), StoreProduct.category.ilike(f"%{word}%")]
    singular = word[:-1] if word.endswith("s") else word
    for english, foreign in ITEM_WORDS.items():
        if word in (english, english + "s") or singular == english:
            options += [StoreProduct.name.ilike(f"%{f}%") for f in foreign]
    return or_(*options)


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
    reach = delivers_clause(country)
    for start in range(len(words)):
        matches = [_word_condition(w) for w in words[start:]]
        rows = (
            await db.execute(
                select(StoreProduct, Store)
                .join(Store, Store.id == StoreProduct.store_id)
                .outerjoin(StorePlan, StorePlan.code == Store.plan_code)
                .where(live, reach, *matches)
                .order_by(
                    func.coalesce(StorePlan.position, 0).desc(),
                    local_first,
                    StoreProduct.is_featured.desc(),
                    StoreProduct.updated_at.desc(),
                )
                .limit(limit)
            )
        ).all()
        if rows:
            return [(p, s) for p, s in rows]
    return []


# -------------------------------------------------------------------- delivery


def countries_field(codes: list[str] | None) -> str | None:
    """["us", "GB"] -> ",US,GB," (None when empty)."""
    clean = sorted({c.strip().upper() for c in codes or [] if c and c.strip()})
    return f",{','.join(clean)}," if clean else None


def countries_list(field: str | None) -> list[str]:
    return [c for c in (field or "").split(",") if c]


def delivers_to(store: Store, product: StoreProduct, country: str | None) -> bool:
    """Can this product reach a shopper in `country`? Unknown country: yes."""
    if not country or store.country == country:
        return True
    mode = product.delivery or store.delivery
    if mode == "worldwide":
        return True
    if mode == "countries" or (product.delivery is None and store.delivery == "countries"):
        return country in countries_list(store.delivery_countries)
    return False


def delivers_clause(country: str | None):  # noqa: ANN201 - a SQL condition
    """delivers_to as a WHERE condition, for search."""
    if not country:
        return true()
    store_reaches = or_(
        Store.delivery == "worldwide",
        and_(Store.delivery == "countries", Store.delivery_countries.like(f"%,{country},%")),
    )
    return or_(
        Store.country == country,
        StoreProduct.delivery == "worldwide",
        and_(StoreProduct.delivery.is_(None), store_reaches),
    )


async def plan_tiers(db: AsyncSession) -> dict[str, int]:
    """Each plan's rank by its place in the plan list: Basic 1, Standard 2, Premium 3."""
    return dict((await db.execute(select(StorePlan.code, StorePlan.position))).all())


async def featured_count(db: AsyncSession, store_id: str) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(StoreProduct)
            .where(StoreProduct.store_id == store_id, StoreProduct.is_active.is_(True), StoreProduct.is_featured.is_(True))
        )
        or 0
    )


async def featured_ids(db: AsyncSession, stores: list[Store]) -> set[str]:
    """The products that count as featured now: each store's featured products,
    newest first, up to its plan's featured limit (a smaller plan after a
    bigger one keeps only that many)."""
    ids: set[str] = set()
    for store in {s.id: s for s in stores}.values():
        if store.plan_featured_limit <= 0 or not plan_active(store):
            continue
        rows = (
            await db.execute(
                select(StoreProduct.id)
                .where(StoreProduct.store_id == store.id, StoreProduct.is_active.is_(True), StoreProduct.is_featured.is_(True))
                .order_by(StoreProduct.updated_at.desc())
                .limit(store.plan_featured_limit)
            )
        ).scalars()
        ids.update(rows)
    return ids


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


# ------------------------------------------------------------------ statistics


async def store_stats(db: AsyncSession, store_id: str, days: int = 30) -> dict:
    """Shop clicks and try-ons of a store's products over the last `days`.

    A store product becomes a saved Product (retailer "stores", its id as the
    retailer product id) the moment a shopper picks it; clicks and try-ons
    are recorded against that Product."""
    from app.models.affiliate import AffiliateClick
    from app.models.outfit import OutfitItem
    from app.models.product import Product
    from app.models.retailer import Retailer
    from app.models.tryon import TryOnJob

    since = utcnow() - timedelta(days=days)
    saved = (
        await db.execute(
            select(Product.id, StoreProduct.id, StoreProduct.name)
            .join(Retailer, Retailer.id == Product.retailer_id)
            .join(StoreProduct, StoreProduct.id == Product.retailer_product_id)
            .where(Retailer.slug == "stores", StoreProduct.store_id == store_id)
        )
    ).all()
    views = await views_by_product(db, store_id, days)
    names = dict((await db.execute(select(StoreProduct.id, StoreProduct.name).where(StoreProduct.id.in_(views)))).all()) if views else {}
    if not saved:
        top = sorted(
            ({"store_product_id": k, "name": names.get(k, ""), "views": v, "clicks": 0, "tryons": 0} for k, v in views.items()),
            key=lambda r: r["views"], reverse=True,
        )[:10]
        return {"days": days, "views": sum(views.values()), "clicks": 0, "tryons": 0, "top": top}
    product_ids = [row[0] for row in saved]
    by_product = {row[0]: {"store_product_id": row[1], "name": row[2], "views": 0, "clicks": 0, "tryons": 0} for row in saved}
    for row in by_product.values():
        row["views"] = views.get(row["store_product_id"], 0)
    seen = {row["store_product_id"] for row in by_product.values()}
    for store_product_id, count in views.items():  # shown but never picked yet
        if store_product_id not in seen:
            by_product[f"view-{store_product_id}"] = {
                "store_product_id": store_product_id, "name": names.get(store_product_id, ""), "views": count, "clicks": 0, "tryons": 0,
            }

    for product_id, count in (
        await db.execute(
            select(AffiliateClick.product_id, func.count())
            .where(AffiliateClick.product_id.in_(product_ids), AffiliateClick.created_at >= since)
            .group_by(AffiliateClick.product_id)
        )
    ).all():
        by_product[product_id]["clicks"] = int(count)

    single = (
        await db.execute(
            select(TryOnJob.product_id, func.count())
            .where(TryOnJob.product_id.in_(product_ids), TryOnJob.created_at >= since)
            .group_by(TryOnJob.product_id)
        )
    ).all()
    in_outfits = (
        await db.execute(
            select(OutfitItem.product_id, func.count(func.distinct(TryOnJob.id)))
            .join(TryOnJob, TryOnJob.outfit_id == OutfitItem.outfit_id)
            .where(OutfitItem.product_id.in_(product_ids), TryOnJob.created_at >= since)
            .group_by(OutfitItem.product_id)
        )
    ).all()
    for product_id, count in [*single, *in_outfits]:
        by_product[product_id]["tryons"] += int(count)

    rows = sorted(by_product.values(), key=lambda r: (r["clicks"] + r["tryons"], r["views"]), reverse=True)
    return {
        "days": days,
        "views": sum(views.values()),
        "clicks": sum(r["clicks"] for r in rows),
        "tryons": sum(r["tryons"] for r in rows),
        "top": [r for r in rows if r["views"] or r["clicks"] or r["tryons"]][:10],
    }


# ---------------------------------------------------------------------- emails


async def notify_owner(db: AsyncSession, store: Store, subject: str, body: str) -> None:
    """One email to the store's contact address (or its owner's). Never raises:
    an email that couldn't be sent must not undo what the admin did."""
    from app.core.logging import logger
    from app.email.registry import get_email_provider
    from app.models.user import User

    to = store.contact_email or await db.scalar(select(User.email).where(User.id == store.owner_user_id))
    if not to:
        return
    site = str(get_settings().FRONTEND_URL).rstrip("/")
    try:
        await get_email_provider().send(
            to=to,
            subject=subject,
            text_body=f"{body}\n\nYour store dashboard: {site}/business\n\nTryOnU",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("store_email_failed", store_id=store.id, error=str(exc)[:200])


STATUS_EMAILS = {
    "approved": (
        "Your TryOnU store is approved",
        "Good news: {name} is approved. Once your plan is active, shoppers see your products, and shoppers in your country see them first.",
    ),
    "rejected": ("Your TryOnU store wasn't approved", "{name} wasn't approved.{note}"),
    "suspended": ("Your TryOnU store is suspended", "{name} is suspended and its products are hidden from shoppers.{note}"),
}


async def send_plan_reminders(db: AsyncSession) -> dict:
    """Emails stores whose plan ends within 3 days, and stores whose plan has
    just ended; each expiry is emailed about once."""
    now = utcnow()
    soon, ended = 0, 0
    stores = (await db.execute(select(Store).where(Store.plan_expires_at.is_not(None)))).scalars().all()
    for store in stores:
        expires = _aware(store.plan_expires_at)
        if now < expires <= now + timedelta(days=3) and _aware(store.reminded_for_expiry) != expires:
            await notify_owner(
                db, store, "Your TryOnU store plan ends soon",
                f"The plan for {store.name} ends on {expires:%d %b %Y}. Renew it to keep your products in front of shoppers.",
            )
            store.reminded_for_expiry = expires
            soon += 1
        elif expires <= now and now - expires < timedelta(days=7) and _aware(store.expired_notice_for) != expires:
            await notify_owner(
                db, store, "Your TryOnU store plan has ended",
                f"The plan for {store.name} ended on {expires:%d %b %Y}, so shoppers no longer see your products. "
                "Renew it any time to bring them back.",
            )
            store.expired_notice_for = expires
            ended += 1
    await db.commit()
    return {"ending_soon": soon, "ended": ended}


# ------------------------------------------------------------------ file import


async def import_store_file(db: AsyncSession, store: Store, data: bytes) -> str:
    """Products from an uploaded CSV/JSON file, added like typed-in ones (kept
    by feed imports). A row whose id matches an earlier upload updates it."""
    try:
        rows = await asyncio.to_thread(parse_feed, data)
    except Exception as exc:  # noqa: BLE001
        return f"Couldn't read the file: {str(exc)[:160]}"
    host_ok = _host_checker()
    items: dict[str, dict] = {}
    skipped = 0
    for row in rows:
        item = await asyncio.to_thread(normalize_feed_row, row, host_ok)
        if item is None:
            skipped += 1
            continue
        items.setdefault(f"f-{item['external_id']}"[:128], item)

    existing = {
        p.external_id: p
        for p in (
            await db.execute(select(StoreProduct).where(StoreProduct.store_id == store.id, StoreProduct.source == "manual"))
        ).scalars()
    }
    room = max(0, store.plan_product_limit - await active_product_count(db, store.id))
    added = updated = over = 0
    for external_id, item in items.items():
        current = existing.get(external_id)
        if current is not None:
            for field, value in item.items():
                if field != "external_id":
                    setattr(current, field, value)
            updated += 1
        elif room > 0:
            db.add(StoreProduct(store_id=store.id, source="manual", **{**item, "external_id": external_id}))
            room -= 1
            added += 1
        else:
            over += 1
    await db.commit()
    return (
        f"Added {added} and updated {updated} products"
        + (f"; {over} more didn't fit your plan's limit of {store.plan_product_limit}" if over else "")
        + (f"; {skipped} rows skipped (missing name, price, link or photo)" if skipped else "")
        + "."
    )


# ------------------------------------------------------- auto-renew (PayPal)

STOPPED = {"CANCELLED", "SUSPENDED", "EXPIRED"}


async def sync_subscription(db: AsyncSession, store: Store, provider) -> str:  # noqa: ANN001
    """Brings a store's auto-renew in line with what PayPal says.

    Each new PayPal payment (a later `last_payment` time than the one already
    counted) adds one plan period and is recorded as a payment, so a payment
    is never counted twice however often this runs. A cancelled, suspended or
    expired subscription turns auto-renew off; the time already paid stays."""
    from app.models.enums import PaymentStatus
    from app.models.subscription import Payment

    if not store.subscription_id:
        return "none"
    info = await provider.store_subscription(store.subscription_id)
    if info.get("custom_id") not in (None, store.id):
        return "mismatch"  # never a subscription made for another store
    status = str(info.get("status") or "")
    store.subscription_status = status
    result = "pending"
    if status == "ACTIVE":
        store.auto_renew = True
        paid_at = _aware(info.get("last_paid_at"))
        counted = _aware(store.subscription_last_paid_at)
        plan = await db.scalar(select(StorePlan).where(StorePlan.code == store.subscription_plan_code))
        if paid_at and (counted is None or paid_at > counted) and plan is not None:
            activate_plan(store, plan)
            store.subscription_last_paid_at = paid_at
            db.add(
                Payment(
                    user_id=store.owner_user_id,
                    amount_cents=info.get("last_paid_cents") or plan.price_cents,
                    currency=info.get("last_paid_currency") or plan.currency,
                    status=PaymentStatus.SUCCEEDED,
                    provider="paypal",
                    external_payment_id=f"{store.subscription_id}:{paid_at.isoformat()}"[:255],
                    store_plan_id=plan.id,
                    store_id=store.id,
                )
            )
            from app.services.referral_service import reward_store_plan

            await reward_store_plan(db, store.owner_user_id, plan)  # only the first plan ever counts
            result = "renewed"
        else:
            result = "active"
    elif status in STOPPED:
        store.auto_renew = False
        result = "stopped"
    await db.commit()
    return result


async def sync_all_subscriptions(db: AsyncSession, provider) -> dict:  # noqa: ANN001
    from app.core.logging import logger

    counts: dict[str, int] = {}
    stores = (await db.execute(select(Store).where(Store.subscription_id.is_not(None)))).scalars().all()
    for store in stores:
        if store.subscription_status in STOPPED:
            continue
        try:
            outcome = await sync_subscription(db, store, provider)
        except Exception as exc:  # noqa: BLE001 — one store must not stop the others
            await db.rollback()
            logger.warning("store_subscription_sync_failed", store_id=store.id, error=str(exc)[:200])
            outcome = "error"
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


# ---------------------------------------------------------------- product views


async def record_views(db: AsyncSession, store_product_ids: list[str]) -> None:
    """One view per store product shown to a shopper, counted per day.
    Never raises: counting must not break the page that shows the products."""
    from app.core.logging import logger

    ids = [i for i in dict.fromkeys(store_product_ids) if i]
    if not ids:
        return
    try:
        today = utcnow().date()
        owners = dict((await db.execute(select(StoreProduct.id, StoreProduct.store_id).where(StoreProduct.id.in_(ids)))).all())
        rows = {
            v.store_product_id: v
            for v in (
                await db.execute(
                    select(StoreProductView).where(StoreProductView.store_product_id.in_(owners), StoreProductView.day == today)
                )
            ).scalars()
        }
        for product_id, store_id in owners.items():
            if product_id in rows:
                rows[product_id].views += 1
            else:
                db.add(StoreProductView(store_id=store_id, store_product_id=product_id, day=today, views=1))
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("store_views_not_counted", error=str(exc)[:200])


async def views_by_product(db: AsyncSession, store_id: str, days: int) -> dict[str, int]:
    since = (utcnow() - timedelta(days=days)).date()
    return {
        pid: int(total or 0)
        for pid, total in (
            await db.execute(
                select(StoreProductView.store_product_id, func.sum(StoreProductView.views))
                .where(StoreProductView.store_id == store_id, StoreProductView.day >= since)
                .group_by(StoreProductView.store_product_id)
            )
        ).all()
    }
