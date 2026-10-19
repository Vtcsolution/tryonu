"""Every "Shop" link on the site reaches the shop, whatever page it's on
(saved looks, community posts, shared looks, photo search, price alerts)."""

from __future__ import annotations

from tests.conftest import seed_product


async def test_shop_links_from_every_page_redirect(client, db):  # noqa: ANN001
    product = await seed_product(db, name="Red Silk Dress")
    for source in ("product_card", "saved_look", "community", "shared_look", "lens", "price_alert", "something_new"):
        res = await client.get(f"/api/v1/affiliate/go/{product.id}?source={source}", follow_redirects=False)
        assert res.status_code == 302, (source, res.status_code)
