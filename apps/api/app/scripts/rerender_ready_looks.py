"""Make every Ready look's outfit picture again with the current design (and
current prices), and keep its layout so tryonu.app can show the product
cards as links. A look whose title names who it's for ("Men's Winter
Outfit") but sits under someone else is moved. Run on the server after an
update that changes the design:

    python -m app.scripts.rerender_ready_looks
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.api.v1.endpoints.ready_looks import _get, _render, guess_audience
from app.db.session import AsyncSessionLocal
from app.models.ready_look import ReadyLook


async def main() -> int:
    async with AsyncSessionLocal() as db:
        ids = list((await db.execute(select(ReadyLook.id).order_by(ReadyLook.created_at))).scalars())
        for look_id in ids:
            look = await _get(db, look_id)
            said, from_title = guess_audience(look.title, [item.product for item in look.items])
            if from_title and said != look.audience:
                print(f"moved  {look.title}: {look.audience} -> {said}")
                look.audience = said
            try:
                await _render(db, look)
                await db.commit()
                print(f"done   {look.title}  ({len(look.items)} products)")
            except Exception as exc:  # noqa: BLE001 - one broken look doesn't stop the rest
                await db.rollback()
                print(f"failed {look.title}: {exc}")
    print(f"{len(ids)} looks")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
