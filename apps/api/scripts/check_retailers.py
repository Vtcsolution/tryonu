"""Which retailers actually answer a live search from this machine?

Run on the box that serves search, with its own .env, because that is
where the answer matters: a key that works from a laptop says nothing
about a key that was never pasted into the server's environment.

    ./.venv/bin/python scripts/check_retailers.py
    ./.venv/bin/python scripts/check_retailers.py --query "gold bridal earrings"

Each registered retailer (see app/retailers/registry.py) is asked the
same real query. A retailer with no credentials in this environment is
reported SKIPPED, not silently missing — that silence, upstream in
live_search_service._ask(), is exactly what makes "only eBay works"
look like a code bug instead of a missing key. Nothing is written to
the database, and no key is printed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.retailers.errors import RetailerNotConfiguredError  # noqa: E402


async def _try(provider, query: str) -> None:  # noqa: ANN001
    label = f"{provider.slug} ({provider.display_name})"
    started = time.time()
    try:
        results = await provider.search_live(query=query, limit=10)
    except NotImplementedError:
        print(f"  {label:28s} SKIPPED  search_live not implemented for this retailer")
        return
    except RetailerNotConfiguredError as exc:
        print(f"  {label:28s} SKIPPED  {exc}")
        return
    except Exception as exc:  # noqa: BLE001 — this script's whole job is to report what broke
        print(f"  {label:28s} FAILED after {time.time() - started:4.0f}s  {type(exc).__name__}: {str(exc)[:160]}")
        return

    took = time.time() - started
    if not results:
        print(f"  {label:28s} OK       {took:4.0f}s  0 results (reachable, but nothing matched)")
        return
    print(f"  {label:28s} OK       {took:4.0f}s  {len(results)} results — e.g. {results[0].name[:60]!r}")


_DEFAULT_QUERY = "black adidas sneakers"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--query", default=_DEFAULT_QUERY, help=f"search term to test with (default: {_DEFAULT_QUERY!r})")
    args = parser.parse_args()

    from app.retailers.registry import get_all_providers

    providers = get_all_providers()
    print(f"query:     {args.query!r}")
    print(f"retailers: {len(providers)} registered")
    print()

    for provider in providers:
        await _try(provider, args.query)

    print()
    print("Also check app.services.live_search_service.live_search() directly if every")
    print("retailer above answers OK but the search box still looks eBay-only — that")
    print("combines them, and a caching or interleaving issue would live there instead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
