"""Show the credit plans, and optionally add the suggested starting plans.

    python -m app.scripts.credit_plans            # list plans: price, credits, try-ons each buys
    python -m app.scripts.credit_plans --apply    # also add any suggested plan not there yet

--apply only ADDS a suggested plan whose name doesn't exist yet; it never
edits, hides or deletes a plan. Prices and credits are then managed in
Admin -> Credit packages, and the try-on cost in Admin -> Settings -> Credits.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.credit import CreditPackage

# name, price in cents (USD), credits. At 10 credits per try-on:
# Starter = 2 try-ons, Popular = 5, Pro = 12.
SUGGESTED = [
    ("Starter", 700, 20),
    ("Popular", 1500, 50),
    ("Pro", 3000, 120),
]


async def main() -> int:
    apply = "--apply" in sys.argv
    cost = max(get_settings().TRYON_CREDIT_COST, get_settings().OUTFIT_TRYON_CREDIT_COST)
    async with AsyncSessionLocal() as db:
        existing = {p.name.lower() for p in (await db.execute(select(CreditPackage))).scalars()}
        if apply:
            for name, price, credits in SUGGESTED:
                if name.lower() not in existing:
                    db.add(CreditPackage(name=name, price_cents=price, credits=credits, currency="usd", is_active=True))
                    print(f"added: {name} ${price / 100:.2f} -> {credits} credits")
            await db.commit()
        packages = (await db.execute(select(CreditPackage).order_by(CreditPackage.price_cents))).scalars().all()
    print(f"\ntry-on cost: {cost} credits")
    for p in packages:
        state = "on sale" if p.is_active else "hidden"
        print(f"  {p.name:<12} {p.price_cents / 100:>7.2f} {p.currency.upper()}  {p.credits:>5} credits  "
              f"= {p.credits // cost} try-ons  ({state})")
    if not packages:
        print("  no plans yet: run with --apply, or create them in Admin -> Credit packages")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
