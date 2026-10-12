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


def current_country() -> str | None:
    return _country.get()


def set_country(code: str | None) -> None:
    _country.set(code.upper() if code and len(code) == 2 else None)


async def use_profile_country(db: AsyncSession, user_id: str | None) -> None:
    """The profile's country, when set, wins over the IP's."""
    if not user_id:
        return
    from app.models.preference import UserPreference

    country = await db.scalar(select(UserPreference.country).where(UserPreference.user_id == user_id))
    if country:
        set_country(country)
