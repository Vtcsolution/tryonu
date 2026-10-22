"""Which country the shopper making this request is in, so local stores come first.

Set once per request by a middleware from the IP (Cloudflare's header or the
MaxMind database, see analytics_service.country_for_request), then replaced
by the country in the shopper's profile where an endpoint knows the user.
Read anywhere in that request through current_country().
"""

from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_country: ContextVar[str | None] = ContextVar("shopper_country", default=None)
# where the shopper likes to shop (their choice after signing up): local | worldwide | both
_shop_from: ContextVar[str | None] = ContextVar("shopper_shop_from", default=None)


def current_country() -> str | None:
    return _country.get()


def current_shop_from() -> str | None:
    return _shop_from.get()


def set_shop_from(choice: str | None) -> None:
    _shop_from.set(choice if choice in ("local", "worldwide", "both") else None)


def set_country(code: str | None) -> None:
    _country.set(code.upper() if code and len(code) == 2 else None)


async def use_profile_country(db: AsyncSession, user_id: str | None) -> None:
    """The profile's country, when set, wins over the IP's; and where they like to shop."""
    if not user_id:
        return
    from app.models.preference import UserPreference

    row = (
        await db.execute(select(UserPreference.country, UserPreference.shop_from).where(UserPreference.user_id == user_id))
    ).first()
    if row is None:
        return
    country, shop_from = row
    if country:
        set_country(country)
    set_shop_from(shop_from)
