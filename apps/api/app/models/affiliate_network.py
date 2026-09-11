from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AffiliateNetwork(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The network that provides affiliate tracking/commission for one or
    more retailers — distinct from the retailer itself. E.g. Amazon's
    catalog might be reached directly, while a mid-size retailer's catalog
    and commission both flow through Awin/CJ/Impact.

    Seeded rows: awin, cj, impact, direct (see app/scripts/seed.py). The
    real per-network integration (report pulls, conversion postbacks) lives
    in app/affiliate_networks/*.py and activates automatically once that
    network's credentials are set — see AffiliateNetworkProvider.
    """

    __tablename__ = "affiliate_networks"

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
