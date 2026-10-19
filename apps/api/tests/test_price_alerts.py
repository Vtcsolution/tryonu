"""Price alerts: a member watches a product; when it gets cheaper (by enough)
or comes back in stock they're told once; small wobbles tell nobody."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.models.price_watch import PriceWatch
from app.services import price_alert_service as svc
from tests.conftest import register_and_login, seed_product


async def test_price_drops_and_back_in_stock(client, db, monkeypatch):  # noqa: ANN001
    product = await seed_product(db, name="Pink Embroidered Lehenga", price_cents=10000)
    await register_and_login(client)
    added = await client.post(f"/api/v1/price-alerts/{product.id}")
    assert added.status_code == 200, added.text
    assert added.json()["start_price_cents"] == 10000
    assert (await client.post(f"/api/v1/price-alerts/{product.id}")).status_code == 200  # once is enough
    assert (await client.get("/api/v1/price-alerts/ids")).json() == [product.id]
    assert (await client.post("/api/v1/price-alerts/not-a-product")).status_code == 404

    shop = {"offer": (9800, "usd", True)}

    async def fake_offer(p):  # noqa: ANN001, ANN202
        return shop["offer"]

    monkeypatch.setattr(svc, "current_offer", fake_offer)

    async def run_check() -> list[dict]:
        await db.execute(update(PriceWatch).values(checked_at=datetime.now(timezone.utc) - timedelta(days=1)))
        await db.commit()
        await svc.check_due(db)
        items = (await client.get("/api/v1/notifications")).json()["items"]
        return [n for n in items if n["kind"] in ("price_drop", "back_in_stock")]

    assert await run_check() == []  # 2% cheaper: not worth a message

    shop["offer"] = (7999, "usd", True)
    notes = await run_check()
    assert len(notes) == 1 and notes[0]["kind"] == "price_drop"
    assert "now $79.99 (was $100.00)" in notes[0]["text"] and notes[0]["url"] == f"/try?product={product.id}"
    assert len(await run_check()) == 1  # same price again: nothing new

    shop["offer"] = (7999, "usd", False)  # sold out...
    assert len(await run_check()) == 1
    shop["offer"] = (8200, "usd", True)  # ...and back
    notes = await run_check()
    assert notes[0]["kind"] == "back_in_stock" and "$82.00" in notes[0]["text"]

    shop["offer"] = (6500, "usd", True)  # cheaper than the last price they heard ($79.99)
    notes = await run_check()
    assert notes[0]["kind"] == "price_drop" and "was $79.99" in notes[0]["text"]

    mine = (await client.get("/api/v1/price-alerts")).json()
    assert mine[0]["price_cents"] == 6500 and mine[0]["in_stock"] is True and mine[0]["name"] == "Pink Embroidered Lehenga"
    assert (await client.delete(f"/api/v1/price-alerts/{product.id}")).status_code == 204
    assert (await client.get("/api/v1/price-alerts")).json() == []
