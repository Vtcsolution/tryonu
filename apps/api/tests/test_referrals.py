"""Share and earn: a friend from your link tries something on (2 credits), a store from your link buys a plan
(10/20/30), and optionally a friend's first purchase: each earns you credits once."""

from __future__ import annotations

from app.core.config import get_settings
from tests.conftest import credit_balance, register_and_login, seed_credit_package
from tests.test_shared_looks import _finished_look


async def _switch_to(client, cookies: dict) -> None:  # noqa: ANN001
    client.cookies.clear()
    for name, value in cookies.items():
        client.cookies.set(name, value)


async def test_a_friend_from_your_invite_link_buys_and_you_earn_once(client, db, monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(get_settings(), "REFERRAL_REWARD_CREDITS", 10)  # off by default; admins can turn it on
    me = await register_and_login(client)
    mine = (await client.get("/api/v1/referrals/me")).json()
    assert mine["link"].endswith(f"/?ref={mine['code']}") and mine["reward_credits"] == get_settings().REFERRAL_REWARD_CREDITS
    assert (await client.get("/api/v1/referrals/me")).json()["code"] == mine["code"]  # the same link every time
    assert (await client.post("/api/v1/referrals/claim", json={"ref": mine["code"]})).json() == {"claimed": False}  # not yourself
    my_cookies = dict(client.cookies)
    before = await credit_balance(db, me["user"]["id"])

    await register_and_login(client)  # the friend
    assert (await client.post("/api/v1/referrals/claim", json={"ref": mine["code"].upper()})).json() == {"claimed": True}
    assert (await client.post("/api/v1/referrals/claim", json={"ref": mine["code"]})).json() == {"claimed": False}  # once
    package = await seed_credit_package(db, credits=50)
    assert (await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})).status_code == 200
    assert (await client.post("/api/v1/credits/purchase", json={"credit_package_id": package.id})).status_code == 200

    reward = get_settings().REFERRAL_REWARD_CREDITS
    assert await credit_balance(db, me["user"]["id"]) == before + reward  # earned once, not per purchase
    await _switch_to(client, my_cookies)
    mine = (await client.get("/api/v1/referrals/me")).json()
    assert (mine["friends_joined"], mine["friends_bought"], mine["credits_earned"]) == (1, 1, reward)


async def test_a_shared_look_counts_as_your_invite(client, db, monkeypatch):  # noqa: ANN001
    job_id, _ = await _finished_look(client, db, monkeypatch)
    token = (await client.post(f"/api/v1/tryon/{job_id}/share")).json()["token"]
    owner_cookies = dict(client.cookies)

    await register_and_login(client)
    assert (await client.post("/api/v1/referrals/claim", json={"ref": f"look:{token}"})).json() == {"claimed": True}
    await _switch_to(client, owner_cookies)
    assert (await client.get("/api/v1/referrals/me")).json()["friends_joined"] == 1


async def test_unknown_links_claim_nothing(client):  # noqa: ANN001
    await register_and_login(client)
    assert (await client.post("/api/v1/referrals/claim", json={"ref": "nobody12"})).json() == {"claimed": False}
    assert (await client.post("/api/v1/referrals/claim", json={"ref": "look:nope"})).json() == {"claimed": False}



async def test_a_friends_first_paid_try_on_earns_you_credits_once(client, db, monkeypatch):  # noqa: ANN001
    from app.ai.providers.base import TryOnOutput
    from app.ai.providers.mock import MockTryOnProvider
    from tests.conftest import seed_product, small_jpeg_bytes
    from tests.test_tryon import _poll_until_terminal, _upload_front_photo

    async def fake_generate(self, payload):  # noqa: ANN001, ANN202, ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes(), provider_job_id="fake-ok", latency_ms=1)

    monkeypatch.setattr(MockTryOnProvider, "generate", fake_generate)
    monkeypatch.setattr(get_settings(), "REFERRAL_TRYON_CREDITS", 2)
    me = await register_and_login(client)
    code = (await client.get("/api/v1/referrals/me")).json()["code"]
    my_cookies = dict(client.cookies)
    before = await credit_balance(db, me["user"]["id"])

    await register_and_login(client)  # the friend joins from the link...
    assert (await client.post("/api/v1/referrals/claim", json={"ref": code})).json() == {"claimed": True}
    photo_id = await _upload_front_photo(client)
    for name in ("Navy Slim Chinos", "White Oxford Shirt"):  # ...and tries on twice
        product = await seed_product(db, name=name)
        job = (await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})).json()
        assert (await _poll_until_terminal(client, job["id"]))["status"] == "completed"

    assert await credit_balance(db, me["user"]["id"]) == before + 2  # once, not per try-on
    await _switch_to(client, my_cookies)
    mine = (await client.get("/api/v1/referrals/me")).json()
    assert (mine["friends_joined"], mine["friends_tried"], mine["credits_earned"]) == (1, 1, 2)


async def test_a_store_from_your_link_buying_a_plan_earns_you_its_reward(client, db):  # noqa: ANN001
    from sqlalchemy import select

    from app.models.store import StorePlan
    from tests.conftest import make_admin

    plan = await db.scalar(select(StorePlan).where(StorePlan.code == "basic"))
    if plan is None:
        plan = StorePlan(code="basic", name="Basic", price_cents=1000, currency="usd", product_limit=50, duration_days=30, position=1)
        db.add(plan)
    plan.referral_credits = 10
    plan.paypal_product_id = plan.paypal_plan_id = plan.paypal_plan_key = None
    await db.commit()

    me = await register_and_login(client)
    code = (await client.get("/api/v1/referrals/me")).json()
    assert {"plan": "Basic", "credits": 10} in code["store_rewards"] and code["store_link"].endswith(f"/sell?ref={code['code']}")
    my_cookies = dict(client.cookies)
    before = await credit_balance(db, me["user"]["id"])

    await register_and_login(client)  # a store owner joins from the link
    assert (await client.post("/api/v1/referrals/claim", json={"ref": code["code"]})).json() == {"claimed": True}
    assert (await client.post("/api/v1/stores", json={"name": "Referred Couture", "country": "PK"})).status_code == 201
    assert (await client.post("/api/v1/stores/me/plans/basic/purchase")).json()["status"] == "succeeded"  # mock provider
    await client.post("/api/v1/stores/me/plans/basic/purchase")  # a second purchase earns nothing more
    assert await credit_balance(db, me["user"]["id"]) == before + 10

    # admins see who invited whom
    data = await register_and_login(client)
    await make_admin(db, data["user"]["id"])
    report = (await client.get("/api/v1/admin/referrals")).json()
    row = next(r for r in report["rows"] if r["inviter_email"] == me["user"]["email"] and r["store_plan"] == "Basic")
    assert row["credits_earned"] == 10 and row["source"] == "invite link"
    await _switch_to(client, my_cookies)
    assert (await client.get("/api/v1/referrals/me")).json()["stores_bought"] == 1
