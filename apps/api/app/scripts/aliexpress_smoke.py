"""Live check of the AliExpress affiliate integration.

    python -m app.scripts.aliexpress_smoke "khussa shoes"

Calls the real API with the credentials in the environment and prints
what came back — names, prices, images and the tracked link that earns
the commission. Prints no credential values. Exits non-zero if anything
is wrong, so it can be used as a deployment check.
"""

from __future__ import annotations

import asyncio
import sys

from app.core.config import get_settings
from app.retailers.aliexpress import AliExpressProductProvider
from app.retailers.errors import RetailerNotConfiguredError

TRACKED = ("s.click.aliexpress.com", "aff_trace_key=", "aff_short_key=")


def _provider() -> AliExpressProductProvider:
    s = get_settings()
    return AliExpressProductProvider(
        app_key=s.ALIEXPRESS_APP_KEY,
        app_secret=s.ALIEXPRESS_APP_SECRET,
        tracking_id=s.ALIEXPRESS_TRACKING_ID,
        ship_to_country=s.ALIEXPRESS_SHIP_TO_COUNTRY,
        currency=s.ALIEXPRESS_CURRENCY,
    )


async def main() -> int:
    query = " ".join(sys.argv[1:]) or "embroidered kurti women"
    s = get_settings()
    print("credentials (presence only):")
    for name, value in (
        ("app key", s.ALIEXPRESS_APP_KEY),
        ("app secret", s.ALIEXPRESS_APP_SECRET),
        ("tracking id", s.ALIEXPRESS_TRACKING_ID),
    ):
        print(f"  {name:12s} {'set' if value else 'MISSING'}")
    print(f"  ships to     {s.ALIEXPRESS_SHIP_TO_COUNTRY}   prices in {s.ALIEXPRESS_CURRENCY}")

    provider = _provider()
    print(f"\nsearching AliExpress for {query!r} ...")
    try:
        found = await provider.search_live(query=query, limit=5)
    except RetailerNotConfiguredError as exc:
        print(f"\nNOT CONFIGURED: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 — this is the diagnostic
        print(f"\nCALL FAILED: {type(exc).__name__}: {str(exc)[:400]}")
        return 1

    if not found:
        print("\nNo products came back. The call worked, so this is either the "
              "query or an account that cannot see products yet.")
        return 1

    print(f"\n{len(found)} product(s):")
    problems = 0
    for product in found:
        link = provider.build_affiliate_url(product.product_url, tracking_tag="tryonu")
        tracked = any(mark in link for mark in TRACKED)
        problems += 0 if tracked else 1
        print(f"\n  {product.name[:72]}")
        print(f"    price   {product.price_cents / 100:.2f} {product.currency.upper()}")
        print(f"    image   {(product.images[0] if product.images else '(none)')[:78]}")
        print(f"    link    {link[:78]}")
        print(f"    tracked {'yes' if tracked else 'NO — this sale would earn nothing'}")

    if problems:
        print(f"\n{problems} product(s) had an untracked link — check the tracking id.")
        return 1
    print("\nAll good: real products, real prices, tracked links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
