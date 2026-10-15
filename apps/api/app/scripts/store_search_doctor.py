"""Why don't a company store's products show for a shopper's prompt? Read-only.

    python -m app.scripts.store_search_doctor --email shopper@example.com \\
        --prompt "women dress with earrings and sandals"

Prints the shopper's country, every live store (country, delivery, products,
featured), and for each item in the prompt: what the store search finds,
what the delivery rule hides from this shopper, and what the relevance check
drops. Changes nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.preference import UserPreference
from app.models.store import Store, StoreProduct
from app.models.user import User
from app.retailers.stores import StoreProductProvider
from app.services import store_service as svc
from app.services.live_search_service import LiveSearchResult, _disabled_retailer_slugs
from app.services.relevance import keep_relevant
from app.services.shopper_context import set_country
from app.services.stylist_service import _extract_search_terms


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="the shopper account used to test")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--gender", default="women")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == args.email.lower()))
        if user is None:
            print(f"No account {args.email}")
            return 1
        country = await db.scalar(select(UserPreference.country).where(UserPreference.user_id == user.id))
        print(f"Shopper {args.email}: country = {country or 'NOT SET (the IP decides; unknown IP = every store shown)'}")

        disabled = await _disabled_retailer_slugs()
        print(f"'stores' switched off in Admin -> Retailers: {'YES (that is the problem)' if 'stores' in disabled else 'no'}")

        print("\nLive stores:")
        for store in (await db.execute(select(Store))).scalars():
            count = await db.scalar(
                select(func.count()).select_from(StoreProduct).where(StoreProduct.store_id == store.id, StoreProduct.is_active.is_(True))
            )
            featured = await svc.featured_count(db, store.id)
            print(
                f"  {store.name}: country {store.country}, delivery {store.delivery}"
                f"{' ' + str(svc.countries_list(store.delivery_countries)) if store.delivery == 'countries' else ''}, "
                f"live {svc.is_live(store)}, {count} products, {featured} featured"
            )

        terms = _extract_search_terms(args.prompt, args.gender)
        print(f"\nThe prompt is searched as: {terms}")
        provider = StoreProductProvider()
        for term in terms:
            everywhere = await svc.search_store_products(db, term, 24, None)
            for_shopper = await svc.search_store_products(db, term, 24, country)
            set_country(country)
            raws = await provider.search_live(query=term, limit=24)
            kept = keep_relevant(
                [LiveSearchResult(provider=provider, raw=r) for r in raws], term, title=lambda r: r.raw.name, keep_at_least=0
            )
            print(f"\n  '{term}':")
            print(f"    store products whose name matches: {len(everywhere)}")
            for p, s in everywhere[:8]:
                print(f"      - [{s.name}] {p.name[:70]}{'  (featured)' if p.is_featured else ''}{'  (no photo!)' if not p.images else ''}")
            hidden = len(everywhere) - len(for_shopper)
            if hidden:
                print(f"    hidden by delivery for this shopper: {hidden}")
            print(f"    shown to the shopper after the relevance check: {len(kept)}")
            dropped = {r.retailer_product_id for r in raws} - {k.raw.retailer_product_id for k in kept}
            for r in raws:
                if r.retailer_product_id in dropped:
                    print(f"      dropped as not relevant: {r.name[:70]}")
            if not everywhere:
                print("    -> no store product name contains this item's word (names are matched word for word)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
