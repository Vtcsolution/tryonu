"""Affiliate click tracking: the click is recorded before the redirect,
and the redirect goes to the real product's real affiliate URL — never a
modified or substituted one."""

from __future__ import annotations

from sqlalchemy import select

from app.models.affiliate import AffiliateClick
from tests.conftest import register_and_login, seed_product


async def test_affiliate_go_redirects_and_records_click(client, db):
    await register_and_login(client)
    product = await seed_product(db, name="Clickable Item")

    resp = await client.get(f"/api/v1/affiliate/go/{product.id}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == product.affiliate_url

    result = await db.execute(select(AffiliateClick).where(AffiliateClick.product_id == product.id))
    clicks = result.scalars().all()
    assert len(clicks) == 1
    assert clicks[0].source == "product_card"


async def test_affiliate_go_unknown_product_is_404(client):
    resp = await client.get("/api/v1/affiliate/go/does-not-exist", follow_redirects=False)
    assert resp.status_code == 404


async def test_affiliate_click_endpoint_works_for_guests(client, db):
    # no register_and_login — affiliate clicks must be recordable
    # for anonymous visitors too, not just signed-in users.
    product = await seed_product(db)

    resp = await client.post("/api/v1/affiliate/click", json={"product_id": product.id, "source": "search"})
    assert resp.status_code == 200
    assert resp.json()["redirect_url"] == product.affiliate_url

    result = await db.execute(select(AffiliateClick).where(AffiliateClick.product_id == product.id))
    click = result.scalars().one()
    assert click.user_id is None
    assert click.source == "search"
