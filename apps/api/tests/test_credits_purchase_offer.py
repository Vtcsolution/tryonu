"""The $1 first-outfit offer: a credit pack only a member's first purchase can buy."""

from __future__ import annotations

from app.models.credit import CreditPackage
from tests.conftest import credit_balance, register_and_login, seed_credit_package


async def _offer(db) -> CreditPackage:  # noqa: ANN001
    offer = CreditPackage(name="First outfit for $1", credits=10, price_cents=100, currency="usd", new_members_only=True)
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer


async def test_the_first_outfit_offer_is_for_a_members_first_purchase_only(client, db):  # noqa: ANN001
    offer = await _offer(db)
    regular = await seed_credit_package(db, name="Popular Pack", credits=150, price_cents=1299)
    try:
        # visitors and new members see it, first
        listed = (await client.get("/api/v1/credits/packages")).json()
        assert listed[0]["id"] == offer.id and listed[0]["new_members_only"] is True

        me = (await register_and_login(client))["user"]
        before = await credit_balance(db, me["id"])
        bought = await client.post("/api/v1/credits/purchase", json={"credit_package_id": offer.id})  # mock settles at once
        assert bought.status_code == 200 and bought.json()["status"] == "succeeded"
        assert await credit_balance(db, me["id"]) == before + 10

        # after a purchase it's gone, and can't be bought again
        listed = (await client.get("/api/v1/credits/packages")).json()
        assert offer.id not in [p["id"] for p in listed] and regular.id in [p["id"] for p in listed]
        again = await client.post("/api/v1/credits/purchase", json={"credit_package_id": offer.id})
        assert again.status_code == 400 and "first purchase" in again.json()["detail"]
    finally:
        for p in (offer, regular):
            p.is_active = False
        await db.commit()
