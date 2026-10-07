"""Admitad programme feeds: import into admitad_feed_items, and search them.

Only programmes whose connection to our ad space is "active" (approved) are
imported; pending ones are skipped until Admitad approves them. A feed the
advertiser hasn't updated for ADMITAD_FEED_MAX_AGE_DAYS is skipped too. Each
programme's rows are replaced only after its new feed downloaded and parsed,
so a failed download keeps yesterday's products. Feeds are read as they
download and the download stops at ADMITAD_FEED_MAX_ROWS products. Feed links carry our account
code, so they are never logged or returned.
"""

from __future__ import annotations

import asyncio
import csv
import itertools
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import and_, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.db.base import new_uuid
from app.models.admitad_feed import AdmitadFeedItem
from app.services.admitad import get_json, get_token

csv.field_size_limit(2**31 - 1)

_BATCH = 1000


@dataclass
class ImportReport:
    campaign_id: int
    name: str
    feeds_used: list[str] = field(default_factory=list)
    feeds_stale: list[str] = field(default_factory=list)
    rows_kept: int = 0
    rows_skipped: int = 0
    capped: bool = False
    error: str | None = None


def parse_price(value: str | None) -> int | None:
    """Cents from "25.99", "25.99 USD", "1,299.00" or "12,50"; None if no price."""
    if not value:
        return None
    text = re.sub(r"[^\d.,]", "", str(value))
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        cents = round(float(text) * 100)
    except ValueError:
        return None
    return cents if cents > 0 else None


def normalize_row(row: dict, campaign_id: int, campaign_name: str) -> dict | None:
    """One feed row in either layout Admitad serves (Yandex-style "name/url/
    picture/currencyId" or Google-style "title/link/image_link"), or None when
    it lacks what a product card needs."""
    get = lambda *keys: next((str(row[k]).strip() for k in keys if row.get(k) not in (None, "")), "")  # noqa: E731
    name = get("name", "title", "model")
    url = get("url", "link")
    image = get("picture", "image_link").split(",")[0].strip()
    offer_id = get("id", "offer_id")
    raw_price = get("price")
    sale = parse_price(get("sale_price"))
    price = sale or parse_price(raw_price)
    if not (name and url and image and offer_id and price):
        return None
    currency = get("currencyId", "currency")
    if not currency:  # Google layout: "25.99 USD"
        found = re.search(r"\b([A-Za-z]{3})\b", raw_price)
        currency = found.group(1) if found else "usd"
    availability = get("available", "availability").lower()
    old = parse_price(get("oldprice")) or (parse_price(raw_price) if sale else None)
    return {
        "id": new_uuid(),
        "campaign_id": campaign_id,
        "campaign_name": campaign_name[:200],
        "offer_id": offer_id[:128],
        "name": name[:512],
        "description": get("description")[:2000] or None,
        "price_cents": price,
        "old_price_cents": old if old and old > price else None,
        "currency": currency.lower()[:8],
        "image_url": image[:1024],
        "product_url": url[:2048],
        "vendor": get("vendor", "brand")[:200] or None,
        "category": get("category_name", "product_type", "categoryId")[:200] or None,
        "available": availability not in ("false", "0", "out of stock", "out_of_stock", "no"),
    }


def _fresh(feed: dict, now: datetime, max_age_days: int) -> bool:
    stamp = feed.get("advertiser_last_update") or feed.get("admitad_last_update")
    if not stamp:
        return True
    try:
        updated = datetime.fromisoformat(str(stamp).replace(" ", "T"))
    except ValueError:
        return True
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return now - updated <= timedelta(days=max_age_days)


def _read_feed(url: str, rows: dict[str, dict], report: ImportReport, max_rows: int, transport=None) -> None:  # noqa: ANN001
    """Read one feed AS IT DOWNLOADS into `rows` (keyed by offer id), and stop
    downloading once the programme has max_rows products: a feed can be
    hundreds of MB, and nothing is ever written to disk."""
    timeout = httpx.Timeout(60, read=300)
    with httpx.Client(follow_redirects=True, timeout=timeout, transport=transport) as client:
        with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"feed download failed: HTTP {resp.status_code}")
            lines = (line + "\n" for line in resp.iter_lines())
            header = next(lines, "").lstrip("\ufeff")
            delimiter = "\t" if "\t" in header else (";" if header.count(";") > header.count(",") else ",")
            for raw in csv.DictReader(itertools.chain([header], lines), delimiter=delimiter):
                item = normalize_row(raw, report.campaign_id, report.name)
                if item is None:
                    report.rows_skipped += 1
                    continue
                rows.setdefault(item["offer_id"], item)
                if len(rows) >= max_rows:
                    report.capped = True
                    return


async def import_campaign(db: AsyncSession, campaign: dict, *, transport=None) -> ImportReport:  # noqa: ANN001
    s = get_settings()
    report = ImportReport(campaign_id=int(campaign["id"]), name=str(campaign.get("name") or ""))
    now = datetime.now(timezone.utc)
    rows: dict[str, dict] = {}
    for feed in campaign.get("feeds_info") or []:
        label = str(feed.get("name") or "feed")
        if not _fresh(feed, now, s.ADMITAD_FEED_MAX_AGE_DAYS):
            report.feeds_stale.append(label)
            continue
        if not feed.get("csv_link"):
            continue
        await asyncio.to_thread(_read_feed, feed["csv_link"], rows, report, s.ADMITAD_FEED_MAX_ROWS, transport)
        report.feeds_used.append(label)
        if report.capped:
            break
    if not report.feeds_used:
        return report  # nothing fresh: keep whatever is there
    await db.execute(delete(AdmitadFeedItem).where(AdmitadFeedItem.campaign_id == report.campaign_id))
    batch = list(rows.values())
    for begin in range(0, len(batch), _BATCH):
        await db.execute(insert(AdmitadFeedItem), batch[begin : begin + _BATCH])
    await db.commit()
    report.rows_kept = len(batch)
    return report


async def approved_campaigns() -> list[dict]:
    """Every programme approved ("active") for our ad space(s), with its feeds."""
    token = await get_token(["websites", "advcampaigns_for_website"])
    spaces = await get_json(token, "/websites/v2/", {"limit": 50})
    spaces = spaces if isinstance(spaces, list) else spaces.get("results") or []
    found: dict[int, dict] = {}
    for space in spaces:
        body = await get_json(token, f"/advcampaigns/website/{space['id']}/", {"limit": 500, "connection_status": "active"})
        for campaign in body if isinstance(body, list) else body.get("results") or []:
            found.setdefault(int(campaign["id"]), campaign)
    return list(found.values())


async def import_all(db: AsyncSession) -> list[ImportReport]:
    reports = []
    campaigns = await approved_campaigns()
    for campaign in campaigns:
        try:
            report = await import_campaign(db, campaign)
        except Exception as exc:  # noqa: BLE001 — one programme must not stop the rest
            await db.rollback()
            report = ImportReport(campaign_id=int(campaign["id"]), name=str(campaign.get("name")), error=str(exc)[:200])
            logger.warning("admitad_import_failed", campaign=report.name, error=report.error)
        reports.append(report)
    # programmes no longer approved: their products leave the shelf
    keep = [int(c["id"]) for c in campaigns]
    gone = delete(AdmitadFeedItem)
    await db.execute(gone.where(AdmitadFeedItem.campaign_id.not_in(keep)) if keep else gone)
    await db.commit()
    return reports


_IGNORED = {"women", "womens", "woman", "men", "mens", "man", "for", "and", "with", "the", "ladies", "girls", "boys", "unisex"}


async def search_feed(db: AsyncSession, query: str, limit: int) -> list[AdmitadFeedItem]:
    """Feed products whose name has every query word, dropping leading words
    until something matches ("black satin midi dress", then "satin midi
    dress", "midi dress", "dress"), so the item itself is always kept."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 3 and w not in _IGNORED]
    for start in range(len(words)):
        conditions = [AdmitadFeedItem.name.ilike(f"%{w}%") for w in words[start:]]
        found = (
            await db.execute(
                select(AdmitadFeedItem)
                .where(and_(*conditions))
                .order_by(AdmitadFeedItem.available.desc(), AdmitadFeedItem.updated_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        if found:
            return list(found)
    return []
