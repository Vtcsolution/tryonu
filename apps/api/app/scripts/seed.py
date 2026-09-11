"""Seeds credit packages and (optionally) an admin user for local dev.

    python -m app.scripts.seed
    python -m app.scripts.seed --admin-email you@example.com --admin-password changeme
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.logging import configure_logging, logger
from app.db.session import AsyncSessionLocal
from app.models.affiliate_network import AffiliateNetwork
from app.models.credit import CreditPackage
from app.services import auth_service

_PACKAGES = [
    {"name": "Starter Pack", "credits": 50, "price_cents": 499, "currency": "usd"},
    {"name": "Popular Pack", "credits": 150, "price_cents": 1299, "currency": "usd"},
    {"name": "Power Pack", "credits": 500, "price_cents": 3999, "currency": "usd"},
]

_AFFILIATE_NETWORKS = [
    {"slug": "direct", "name": "Direct"},
    {"slug": "awin", "name": "Awin"},
    {"slug": "cj", "name": "CJ Affiliate"},
    {"slug": "impact", "name": "Impact"},
]


async def seed_credit_packages() -> None:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(CreditPackage))).scalars().all()
        existing_names = {p.name for p in existing}
        for pkg in _PACKAGES:
            if pkg["name"] not in existing_names:
                db.add(CreditPackage(**pkg, is_active=True))
        await db.commit()
        logger.info("seeded_credit_packages", count=len(_PACKAGES))


async def seed_affiliate_networks() -> None:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(AffiliateNetwork))).scalars().all()
        existing_slugs = {n.slug for n in existing}
        for net in _AFFILIATE_NETWORKS:
            if net["slug"] not in existing_slugs:
                db.add(AffiliateNetwork(**net, is_active=True))
        await db.commit()
        logger.info("seeded_affiliate_networks", count=len(_AFFILIATE_NETWORKS))


async def seed_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select as _select

        from app.models.user import User

        existing = (await db.execute(_select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            existing.is_admin = True
            await db.commit()
            logger.info("admin_flag_set_on_existing_user", email=email)
            return

        user = await auth_service.register_user(db, email=email, password=password, full_name="Admin")
        user.is_admin = True
        await db.commit()
        logger.info("admin_user_created", email=email)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
    args = parser.parse_args()

    configure_logging(debug=False)
    await seed_credit_packages()
    await seed_affiliate_networks()
    if args.admin_email and args.admin_password:
        await seed_admin(args.admin_email, args.admin_password)


if __name__ == "__main__":
    asyncio.run(main())
