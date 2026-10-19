"""Find the look: search the shops with a photo, like Google Lens.

1. Look at the photo (OpenAI vision) and list every fashion item worn or
   carried: what it is, its colour, pattern and material, the words a shop
   would use for it, and where it is in the picture.
2. For each item, search every connected shop at once (TryOnU stores,
   Admitad, eBay, AliExpress, ... through live_search), with the precise
   words first and broader ones when the precise ones find little.
3. Compare: the item, cut out of the photo, is shown next to the products'
   own photos, and each product gets a score for how close it is: the same
   product ("exact match"), or the nearest alternatives ("similar").

Nothing is invented: every result is a real listing from a real shop, and
the comparison only orders and labels them."""

from __future__ import annotations

import asyncio
import base64
import io
import re
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.logging import logger
from app.schemas.product import LiveProductOut
from app.services import image_service  # noqa: F401 (registers the HEIC decoder)
from app.services.live_search_service import LiveSearchResult, live_search, match_score, to_live_product_out

MAX_ITEMS = 6
PER_ITEM = 12  # products shown for each item
COMPARE = 20  # products compared by eye for each item...
BATCH = 10  # ...this many in one look (the looks run at the same time)
EXACT_AT = 85  # "exact match": the eye says it's the same product, and scores it this high
CLOSE_AT = 75  # "very close": the same kind of item, colour and look

CATEGORIES = (
    "top", "bottom", "dress", "full_outfit", "outerwear", "shoes", "bag", "jewellery", "watch", "eyewear",
    "headwear", "scarf", "belt", "other",
)


class LensError(Exception):
    pass


@dataclass
class Item:
    label: str
    category: str
    query: str
    broad_query: str
    color: str | None
    details: str | None
    box: list[float]  # x0, y0, x1, y1 as fractions of the photo
    matches: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------ pictures


def prepare_photo(raw: bytes) -> tuple[bytes, int, int]:
    """Any photo or screenshot (JPEG, PNG, WebP, HEIC), upright, at most 1600px, as JPEG."""
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That file isn't a photo we can read. Try a JPG or PNG.") from exc
    img.thumbnail((1600, 1600))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue(), img.width, img.height


def _crop(photo: bytes, box: list[float], pad: float = 0.06) -> bytes:
    """The item cut out of the photo, with a little room around it."""
    with Image.open(io.BytesIO(photo)) as img:
        w, h = img.size
        x0, y0, x1, y1 = box
        x0, y0 = max(0.0, x0 - pad), max(0.0, y0 - pad)
        x1, y1 = min(1.0, x1 + pad), min(1.0, y1 + pad)
        if x1 - x0 < 0.05 or y1 - y0 < 0.05:
            region = img.copy()
        else:
            region = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        region.thumbnail((640, 640))
        out = io.BytesIO()
        region.convert("RGB").save(out, "JPEG", quality=86)
        return out.getvalue()


def _part(jpeg: bytes, detail: str = "low") -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode(), "detail": detail}}


def small_photo_url(url: str) -> str:
    """The shop's own smaller copy of a photo where it has one: eBay's s-l1600 is 1600px wide."""
    url = re.sub(r"(i\.ebayimg\.com/.*/s-l)\d+(\.\w+)$", r"\g<1>400\2", url)
    if re.search(r"(alicdn\.com|aliexpress-media\.com)/.+\.(jpe?g|png|webp)$", url, re.IGNORECASE):
        url += "_350x350.jpg"
    return url


def _fetch_small(url: str) -> bytes:
    from app.services.safe_fetch import fetch_limited

    try:
        return fetch_limited(small_photo_url(url), max_bytes=5 * 1024 * 1024, timeout=10.0)
    except Exception:  # noqa: BLE001 — the shop's small copy missing: the full photo
        return fetch_limited(url, max_bytes=8 * 1024 * 1024, timeout=12.0)


def _thumbnail(url: str) -> bytes | None:
    """A product's own photo, small, fetched safely (public addresses only)."""
    try:
        data = _fetch_small(url)
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            img.thumbnail((320, 320))
            out = io.BytesIO()
            img.save(out, "JPEG", quality=82)
            return out.getvalue()
    except Exception:  # noqa: BLE001 — a product without a usable photo is judged by its title
        return None


# ------------------------------------------------------------------ 1. what is in the photo

_ANALYSE = """You are a fashion expert helping a shopper find the clothes in a photo, like Google Lens.
List every clearly visible fashion item the person wears or carries (clothes, shoes, bag, jewellery, watch,
glasses, hat, scarf, belt). Ignore the background, furniture, phones and anything not worn or carried.
If the photo shows a product on its own (no person), list that product.

Answer as JSON:
{"gender": "women|men|kids|unisex",
 "summary": "one short friendly sentence describing the look",
 "items": [{"label": "short name, e.g. Embroidered kurta",
            "category": "one of: top, bottom, dress, full_outfit, outerwear, shoes, bag, jewellery, watch, eyewear, headwear, scarf, belt, other",
            "query": "3 to 6 plain shopping words a shop search understands: gender, colour, key material or pattern, the item. e.g. women pink embroidered chiffon kurta",
            "broad_query": "2 to 3 words for similar items, e.g. women kurta",
            "color": "main colour",
            "details": "pattern, material, cut, notable details in a few words",
            "brand": "only if a logo or brand is clearly readable, else null",
            "box": [x0, y0, x1, y1]}]}

Rules: at most 6 items, the most noticeable first. "box" is a tight box around the item as fractions of the
photo's width and height (0 to 1, top-left origin). Use the words shoppers use, including South Asian names
when they fit (kurta, shalwar kameez, lehenga, saree, dupatta, sherwani, khussa, jhumka). A full matching suit
(e.g. a 3-piece shalwar kameez or a lehenga set) is one "full_outfit" item. No person and no product: "items": []."""


async def _vision(instructions: str, content: list[dict]) -> dict:
    from app.services.tryon_quality.vision import VisionError, ask_json

    try:
        return await ask_json(instructions, content, timeout=90.0)
    except VisionError as exc:
        raise LensError(str(exc)) from exc


def _clean_box(raw: object) -> list[float]:
    try:
        x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in raw)  # type: ignore[union-attr]
    except (TypeError, ValueError):
        return [0.0, 0.0, 1.0, 1.0]
    if x1 <= x0 or y1 <= y0:
        return [0.0, 0.0, 1.0, 1.0]
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def _words(text: object, limit: int = 8) -> str:
    """Plain words only (no punctuation a shop search trips over), at most `limit`."""
    if not text:
        return ""
    return " ".join(re.findall(r"[A-Za-z0-9'&-]+", str(text))[:limit])


async def analyse(photo: bytes) -> tuple[str, str, list[Item]]:
    """(gender, summary, items) for a photo."""
    reply = await _vision(_ANALYSE, [{"type": "text", "text": "Find the fashion items in this photo."}, _part(photo, "high")])
    items: list[Item] = []
    for raw in (reply.get("items") or [])[:MAX_ITEMS]:
        if not isinstance(raw, dict):
            continue
        query = _words(raw.get("query"))
        label = str(raw.get("label") or "").strip()[:60]
        if not query or not label:
            continue
        category = str(raw.get("category") or "other").lower()
        brand = _words(raw.get("brand"), 3) if raw.get("brand") else ""
        if brand and brand.lower() not in query.lower():
            query = f"{brand} {query}"
        items.append(
            Item(
                label=label[0].upper() + label[1:],
                category=category if category in CATEGORIES else "other",
                query=query,
                broad_query=_words(raw.get("broad_query"), 4) or " ".join(query.split()[-2:]),
                color=str(raw.get("color") or "").strip()[:30] or None,
                details=str(raw.get("details") or "").strip()[:120] or None,
                box=_clean_box(raw.get("box")),
            )
        )
    gender = str(reply.get("gender") or "unisex").lower()
    return gender, str(reply.get("summary") or "").strip()[:200], items


# ------------------------------------------------------------------ 2. search the shops


async def _candidates(item: Item) -> list[LiveSearchResult]:
    found = await live_search(item.query, limit=24)
    if len(found) < 8 and item.broad_query and item.broad_query.lower() != item.query.lower():
        more = await live_search(item.broad_query, limit=24)
        seen = {(r.provider.slug, r.raw.retailer_product_id) for r in found}
        found = found + [r for r in more if (r.provider.slug, r.raw.retailer_product_id) not in seen]
    return found


# ------------------------------------------------------------------ 3. compare by eye

_COMPARE = """You compare a fashion item from a shopper's photo (picture 0) with shop products (numbered photos).
For every product give:
- "score": 0-100, how close it is to the item. 90-100: the same product (same design, colour and pattern).
  70-89: very close (same kind of item, same colour and a very similar pattern/cut). 40-69: similar style.
  10-39: same kind of item but a different look. 0-9: a different kind of item.
Give a score for EVERY numbered product, in order.
- "same": true only if it is clearly the same product: its distinctive details match (print or embroidery,
  logo, unusual cut, trims, hardware). Plain basics (plain black leggings, a plain white T-shirt, plain boots)
  can't be told apart, so for them "same" is false even when the score is high.
Judge the product's photo first and its title second. Answer as JSON: {"scores": [{"n": 1, "score": 87, "same": true}, ...]}"""


async def _photo(url: str, downloads: asyncio.Semaphore) -> bytes | None:
    async with downloads:
        return await asyncio.to_thread(_thumbnail, url)


async def _score_batch(item: Item, crop: bytes, batch: list[tuple[int, LiveSearchResult, bytes]]) -> dict[int, tuple[int, bool]]:
    """One look by eye at the item next to a few products: {product number: (score, same)}."""
    content: list[dict] = [
        {"type": "text", "text": f"Picture 0: the shopper's {item.label} ({item.details or item.color or ''})."},
        _part(crop, "low"),
    ]
    # numbered 1, 2, 3... within this look; mapped back to the product's place in the whole list
    for shown, (_, r, thumb) in enumerate(batch, start=1):
        content.append({"type": "text", "text": f"Product {shown}: {r.raw.name[:120]}"})
        content.append(_part(thumb, "low"))
    scores: dict[int, tuple[int, bool]] = {}
    try:
        reply = await asyncio.wait_for(_vision(_COMPARE, content), timeout=45)
    except (LensError, asyncio.TimeoutError) as exc:
        logger.warning("lens_compare_failed", item=item.label, error=str(exc)[:160])
        return scores
    for s in reply.get("scores") or []:
        try:
            shown = int(s["n"])
            if 1 <= shown <= len(batch):
                scores[batch[shown - 1][0]] = (max(0, min(100, int(s.get("score", 0)))), bool(s.get("same")))
        except (KeyError, TypeError, ValueError):
            continue
    return scores


async def _compare(
    item: Item, crop: bytes, found: list[LiveSearchResult], downloads: asyncio.Semaphore
) -> tuple[list[tuple[LiveSearchResult, int, bool]], list[tuple[LiveSearchResult, int, bool]]]:
    """(compared by eye, best first; the rest judged by their titles only)."""
    pool = found[:COMPARE]
    thumbs = await asyncio.gather(*(_photo(r.raw.images[0], downloads) if r.raw.images else _none() for r in pool))
    with_photo = [(n, r, t) for n, (r, t) in enumerate(zip(pool, thumbs), start=1) if t is not None]
    batches = [with_photo[i : i + BATCH] for i in range(0, len(with_photo), BATCH)]
    scores: dict[int, tuple[int, bool]] = {}
    for part in await asyncio.gather(*(_score_batch(item, crop, b) for b in batches)):
        scores.update(part)
    logger.info("lens_compared", item=item.label, photos=len(with_photo), scored=len(scores))
    seen, rest = [], []
    for n, r in enumerate(found, start=1):
        if n in scores:
            score, same = scores[n]
            seen.append((r, score, same and score >= EXACT_AT))
        else:  # not compared by eye: judged by its title, never above "similar"
            rest.append((r, min(60, 25 + 8 * match_score(item.query, r.raw.name)), False))
    seen.sort(key=lambda t: (-t[1], -match_score(item.query, t[0].raw.name)))
    rest.sort(key=lambda t: -t[1])
    return seen, rest


async def _none() -> None:
    return None


async def _matches_for(item: Item, photo: bytes, downloads: asyncio.Semaphore) -> list[dict]:
    try:
        found = await _candidates(item)
    except Exception as exc:  # noqa: BLE001 — one item's search failing must not sink the others
        logger.warning("lens_search_failed", item=item.label, error=str(exc)[:160])
        return []
    if not found:
        return []
    seen, rest = await _compare(item, _crop(photo, item.box), found, downloads)
    # what the eye found close enough; a different kind of item is never shown
    good = [t for t in seen if t[1] >= 25]
    if len(good) < 4:  # always the nearest few: the eye's next best, then by title
        good += [t for t in seen if t[1] < 25 and t[1] >= 10][: 4 - len(good)]
        good += rest[: max(0, 4 - len(good))]
    out = []
    for r, score, exact in good[:PER_ITEM]:
        product: LiveProductOut = to_live_product_out(r)
        product.search_term = item.query
        match = "exact" if exact else "close" if score >= CLOSE_AT else "similar"
        out.append({"product": product.model_dump(), "score": score, "match": match})
    return out


async def find_the_look(photo: bytes) -> dict:
    """The whole answer for one photo: the items found, and for each the shop products, closest first."""
    if not get_settings().OPENAI_API_KEY:
        raise LensError("Photo search isn't switched on yet.")
    gender, summary, items = await analyse(photo)
    downloads = asyncio.Semaphore(16)  # product photos fetched at once, across every item
    results = await asyncio.gather(*(_matches_for(item, photo, downloads) for item in items))
    for item, matches in zip(items, results):
        item.matches = matches
    return {
        "gender": gender,
        "summary": summary,
        "items": [
            {
                "label": i.label, "category": i.category, "query": i.query, "color": i.color, "details": i.details,
                "box": i.box, "matches": i.matches,
            }
            for i in items
        ],
    }
