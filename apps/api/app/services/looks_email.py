"""The "trending looks" sales email: up to 10 Ready looks as picture cards
(the outfit picture, its name, what the pieces cost, "Try it on you"), how
TryOnU works in three steps, and one big button. Trending = the most shop
clicks on a look's products in the last 30 days, then the team's order.

Email programs ignore modern page layout, so this is the old, safe kind:
tables, inline styles, pictures with a fixed width that shrink on phones."""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

SITE = "https://tryonu.app"
SAGE = "#57634f"
INK = "#1c1b17"
MUTED = "#6f6c64"
_SYMBOL = {"usd": "$", "gbp": "£", "eur": "€", "pkr": "Rs ", "inr": "₹", "aed": "AED "}


def _track(path: str, campaign: str) -> str:
    sep = "&" if "?" in path else "?"
    return f"{SITE}{path}{sep}{urlencode({'utm_source': 'email', 'utm_medium': 'email', 'utm_campaign': campaign})}"


def _money(cents: int | None, currency: str | None) -> str:
    if not cents or not currency:
        return ""
    symbol = _SYMBOL.get(currency.lower(), currency.upper() + " ")
    return f"{symbol}{cents / 100:,.2f}"


# words in a message that say which looks fit it (matched in a look's title or season)
_TOPICS = (
    "winter", "summer", "spring", "autumn", "eid", "bridal", "wedding", "mehndi", "party", "casual", "office",
    "formal", "sherwani", "lehenga", "coat", "jacket", "dress", "sneakers", "boots", "eastern", "western",
)


async def pick_looks(db: AsyncSession, text: str, limit: int = 10) -> list[dict]:
    """The looks that fit what the admin wrote ("men's winter...": men's
    looks with "winter" in them), then the trending ones to fill up to `limit`."""
    from app.api.v1.endpoints.ready_looks import _named

    words = text.lower()
    who = _named(words)
    topics = [t for t in _TOPICS if re.search(rf"\b{t}s?\b", words)]
    picked = await trending_looks(db, limit, audience=who, topics=topics) if (who or topics) else []
    if len(picked) < limit:
        seen = {lk["id"] for lk in picked}
        picked += [lk for lk in await trending_looks(db, limit * 2) if lk["id"] not in seen][: limit - len(picked)]
    return picked


async def trending_looks(
    db: AsyncSession, limit: int = 10, *, audience: str | None = None, topics: list[str] | None = None
) -> list[dict]:
    """The looks for the email, as plain data (title, picture, link, price)."""
    from sqlalchemy import or_

    from app.api.v1.endpoints.ready_looks import _LOAD, _LOAD_RETAILER, _out
    from app.models.affiliate import AffiliateClick
    from app.models.ready_look import ReadyLook, ReadyLookItem

    since = datetime.now(timezone.utc) - timedelta(days=30)
    clicks = (
        select(ReadyLookItem.look_id, func.count(AffiliateClick.id).label("n"))
        .join(AffiliateClick, AffiliateClick.product_id == ReadyLookItem.product_id)
        .where(AffiliateClick.created_at >= since)
        .group_by(ReadyLookItem.look_id)
        .subquery()
    )
    stmt = (
        select(ReadyLook)
        .outerjoin(clicks, clicks.c.look_id == ReadyLook.id)
        .where(ReadyLook.is_published.is_(True), ReadyLook.card_key.is_not(None))
    )
    if audience:
        stmt = stmt.where(ReadyLook.audience == audience)
    if topics:
        stmt = stmt.where(
            or_(*[func.lower(ReadyLook.title).like(f"%{t}%") for t in topics],
                *[func.lower(ReadyLook.season).like(f"%{t}%") for t in topics])
        )
    rows = (
        await db.execute(
            stmt.options(_LOAD, _LOAD_RETAILER)
            .order_by(func.coalesce(clicks.c.n, 0).desc(), ReadyLook.sort_order.desc(), ReadyLook.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    looks = []
    for look in rows:
        out = _out(look)
        looks.append({
            "id": out.id,
            "title": out.title,
            "picture": out.card_small_url,
            "pieces": len(out.items),
            "price": _money(out.total_cents, out.currency),
            "url": _track(f"/looks/{out.id}", "trending_looks"),
        })
    return looks


def _button(label: str, url: str, *, big: bool = False) -> str:
    pad = "15px 30px" if big else "10px 18px"
    size = "17px" if big else "14px"
    return (
        f'<a href="{html.escape(url)}" style="display:inline-block;background:{SAGE};color:#ffffff;'
        f'text-decoration:none;font-weight:bold;font-size:{size};padding:{pad};border-radius:999px">{html.escape(label)}</a>'
    )


def _card(look: dict) -> str:
    sub = f"{look['pieces']} pieces" + (f" · {look['price']}" if look["price"] else "")
    return (
        '<td class="col" width="50%" valign="top" style="padding:8px">'
        f'<a href="{html.escape(look["url"])}" style="text-decoration:none">'
        f'<img src="{html.escape(look["picture"])}" width="262" alt="{html.escape(look["title"])}" '
        'style="display:block;width:100%;max-width:262px;height:auto;border:0;border-radius:14px"></a>'
        f'<p style="margin:10px 2px 2px;font:bold 15px Arial,Helvetica,sans-serif;color:{INK}">{html.escape(look["title"])}</p>'
        f'<p style="margin:0 2px 10px;font:13px Arial,Helvetica,sans-serif;color:{MUTED}">{html.escape(sub)}</p>'
        f'<div style="padding:0 2px">{_button("Try it on you →", look["url"])}</div>'
        "</td>"
    )


def render_looks(intro_html: str, intro_text: str, looks: list[dict], footer: str) -> tuple[str, str]:
    """The whole email: intro (already personalised), the looks, how it works, the offer."""
    grid = ""
    for start in range(0, len(looks), 2):
        pair = looks[start : start + 2]
        cells = "".join(_card(lk) for lk in pair) + ("" if len(pair) == 2 else '<td class="col" width="50%"></td>')
        grid += f"<tr>{cells}</tr>"
    steps = [
        ("1", "Upload one photo", "A clear photo of you, standing."),
        ("2", "Pick a look", "Every piece is a real product from a real shop."),
        ("3", "See it on you", "The whole outfit on your own photo in about a minute. Buy only what you love."),
    ]
    steps_html = "".join(
        '<td class="col" width="33%" valign="top" style="padding:8px;text-align:center">'
        f'<div style="width:34px;height:34px;line-height:34px;margin:0 auto;border-radius:999px;background:{SAGE};'
        f'color:#fff;font:bold 15px Arial,Helvetica,sans-serif">{n}</div>'
        f'<p style="margin:8px 0 2px;font:bold 14px Arial,Helvetica,sans-serif;color:{INK}">{html.escape(t)}</p>'
        f'<p style="margin:0;font:13px Arial,Helvetica,sans-serif;color:{MUTED}">{html.escape(d)}</p></td>'
        for n, t, d in steps
    )
    all_looks = _track("/looks", "trending_looks")
    page = f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>@media (max-width:600px){{ .col{{display:block!important;width:100%!important}} }}</style></head>
<body style="margin:0;background:#f6f3ee">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f3ee"><tr><td align="center" style="padding:24px 10px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px">
<tr><td style="padding:0 8px 16px;font:bold 24px Georgia,serif;color:{SAGE}">TryOnU</td></tr>
<tr><td style="background:#ffffff;border:1px solid #e5ddd3;border-radius:18px;padding:22px 20px;font:15px/1.55 Arial,Helvetica,sans-serif;color:{INK}">
{intro_html}
<div style="margin-top:6px">{_button("See all looks", all_looks)}</div>
</td></tr>
<tr><td style="padding:22px 8px 6px;font:bold 20px Georgia,serif;color:{INK}">Trending looks this week</td></tr>
<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{grid}</table></td></tr>
<tr><td style="padding:22px 8px 6px;font:bold 20px Georgia,serif;color:{INK}">How it works</td></tr>
<tr><td style="background:#ffffff;border:1px solid #e5ddd3;border-radius:18px;padding:10px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{steps_html}</tr></table></td></tr>
<tr><td align="center" style="padding:26px 8px 8px">
<p style="margin:0 0 6px;font:bold 19px Georgia,serif;color:{INK}">What will your final look be?</p>
<p style="margin:0 0 16px;font:14px Arial,Helvetica,sans-serif;color:{MUTED}">New to TryOnU? Your first complete outfit costs just $1.</p>
{_button("Try a look on you", all_looks, big=True)}
</td></tr>
<tr><td style="padding:22px 8px 0;font:12.5px/1.5 Arial,Helvetica,sans-serif;color:#8a8a80">{footer}</td></tr>
</table></td></tr></table></body></html>"""

    lines = [intro_text, "", "Trending looks this week:"]
    for lk in looks:
        lines.append(f"- {lk['title']} ({lk['pieces']} pieces{', ' + lk['price'] if lk['price'] else ''}): {lk['url']}")
    lines += [
        "",
        "How it works: 1. Upload one photo. 2. Pick a look. 3. See the whole outfit on you in about a minute, then buy only what you love.",
        "",
        "New to TryOnU? Your first complete outfit costs just $1.",
        f"See all looks: {all_looks}",
    ]
    return "\n".join(lines), page
