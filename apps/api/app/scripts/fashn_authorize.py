"""Operator-only: authorize (or close) the controlled live FASHN spend.

    python -m app.scripts.fashn_authorize --status
    python -m app.scripts.fashn_authorize --credits 2 --phrase "AUTHORIZE 2 FASHN CREDITS"
    python -m app.scripts.fashn_authorize --close

Authorizing creates ONE row in the database that lets the application reserve
FASHN credits, up to the amount named in the phrase, for two hours. Nothing about it lives in .env or in an
environment variable, so a server cannot spend simply because FASHN_API_KEY
exists. Prints no secrets and calls FASHN not at all.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.db.session import AsyncSessionLocal
from app.services.fashn_guard import GuardRefused, close_authorizations, create_authorization, guard_status


async def _run(args: argparse.Namespace) -> int:
    async with AsyncSessionLocal() as db:
        if args.close:
            print(f"closed {await close_authorizations(db)} open authorization(s)")
        elif args.phrase is not None:
            try:
                if args.credits is None:
                    print("REFUSED: --credits is required with --phrase")
                    return 1
                authorization = await create_authorization(
                    db, args.credits, args.phrase, created_by=args.by, note=args.note
                )
            except GuardRefused as exc:
                print(f"REFUSED: {exc}")
                return 1
            print(f"authorized: id={authorization.id} budget={authorization.budget_credits} credits, expires {authorization.expires_at}")
        status = await guard_status(db)
        print(status)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--credits", type=int, help="the most real FASHN credits this authorization allows")
    parser.add_argument("--phrase", help='the exact approval phrase, e.g. "AUTHORIZE 20 FASHN CREDITS"')
    parser.add_argument("--close", action="store_true", help="close every open authorization")
    parser.add_argument("--status", action="store_true", help="only show the guard's state")
    parser.add_argument("--by", default="operator")
    parser.add_argument("--note")
    sys.exit(asyncio.run(_run(parser.parse_args())))


if __name__ == "__main__":
    main()
