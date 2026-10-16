"""Share and earn: a friend who joins from your link and buys credits earns you credits, once."""

from __future__ import annotations

from app.core.config import get_settings
from tests.conftest import credit_balance, register_and_login, seed_credit_package
from tests.test_shared_looks import _finished_look


async def _switch_to(client, cookies: dict) -> None:  # noqa: ANN001
    client.cookies.clear()
    for name, value in cookies.items():
        client.cookies.set(name, value)


async def test_a_friend_from_your_invite_link_buys_and_you_earn_once(client, db):  # noqa: ANN001
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
