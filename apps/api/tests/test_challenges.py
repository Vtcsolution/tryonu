""""Buy or skip?" polls on posts, and weekly style challenges: entries,
the most-liked looks winning credits, trophies and notifications."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.models.community import Challenge
from app.services import challenge_service
from tests.conftest import make_admin, register_and_login, small_jpeg_bytes
from tests.test_community import _as
from tests.test_shared_looks import _finished_look


def _when(**delta) -> str:  # noqa: ANN003
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


async def test_buy_or_skip_votes(client, db, monkeypatch):  # noqa: ANN001
    job_id, _ = await _finished_look(client, db, monkeypatch)  # member A
    a = dict(client.cookies)
    post = (await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True, "poll": True})).json()
    assert post["poll"] is True and (post["poll_buy"], post["poll_skip"], post["my_vote"]) == (0, 0, None)
    url = f"/api/v1/community/posts/{post['id']}/vote"
    assert (await client.post(url, json={"choice": "buy"})).status_code == 400  # not on my own look

    await register_and_login(client)  # member B
    assert (await client.post(url, json={"choice": "maybe"})).status_code == 422
    assert (await client.post(url, json={"choice": "buy"})).json() == {"my_vote": "buy", "poll_buy": 1, "poll_skip": 0}
    assert (await client.post(url, json={"choice": "skip"})).json() == {"my_vote": "skip", "poll_buy": 0, "poll_skip": 1}  # changed my mind
    seen = (await client.get(f"/api/v1/community/posts/{post['id']}")).json()
    assert (seen["my_vote"], seen["poll_skip"]) == ("skip", 1)
    assert (await client.delete(url)).json() == {"my_vote": None, "poll_buy": 0, "poll_skip": 0}
    await client.post(url, json={"choice": "buy"})

    await _as(client, a)
    note = (await client.get("/api/v1/notifications")).json()["items"][0]
    assert note["kind"] == "poll_vote" and "voted" in note["text"] and note["url"] == f"/community/post/{post['id']}"
    photo = await client.post(
        "/api/v1/community/posts/media", files={"file": ("p.jpg", small_jpeg_bytes(), "image/jpeg")}, data={"accept_rules": "true"}
    )
    client.cookies.clear()
    await register_and_login(client)
    assert (await client.post(f"/api/v1/community/posts/{photo.json()['id']}/vote", json={"choice": "buy"})).status_code == 400  # no poll


async def test_a_weekly_challenge_from_start_to_winners(client, db, monkeypatch):  # noqa: ANN001
    job_id, _ = await _finished_look(client, db, monkeypatch)  # member A
    a = dict(client.cookies)
    a_handle = (await client.get("/api/v1/community/me")).json()["handle"]
    a_credits = (await client.get("/api/v1/auth/me")).json()["credits_balance"]

    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    admin_cookies = dict(client.cookies)
    bad = await client.post("/api/v1/admin/community/challenges", json={"title": "Oops", "starts_at": _when(days=2), "ends_at": _when(days=1)})
    assert bad.status_code == 400  # ends before it starts
    made = await client.post(
        "/api/v1/admin/community/challenges",
        json={"title": "Eid Look Week", "description": "Show your best Eid outfit.", "starts_at": _when(hours=-1), "ends_at": _when(days=7)},
    )
    assert made.status_code == 201, made.text
    ch = made.json()
    assert ch["state"] == "live" and ch["prizes"] == [50, 30, 20]
    later = (
        await client.post(
            "/api/v1/admin/community/challenges",
            json={"title": "Summer Casual", "starts_at": _when(days=8), "ends_at": _when(days=15), "prize_1": 100},
        )
    ).json()

    # A enters with a try-on look; one entry per member; not yet open: no entries
    await _as(client, a)
    listed = (await client.get("/api/v1/community/challenges")).json()
    assert ch["id"] in [c["id"] for c in listed["live"]] and later["id"] in [c["id"] for c in listed["upcoming"]]
    entry_a = (
        await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True, "challenge_id": ch["id"]})
    ).json()
    assert entry_a["challenge"] == {"id": ch["id"], "title": "Eid Look Week"}
    photo = {"file": ("p.jpg", small_jpeg_bytes(), "image/jpeg")}
    again = await client.post("/api/v1/community/posts/media", files=photo, data={"accept_rules": "true", "challenge_id": ch["id"]})
    assert again.status_code == 409
    early = await client.post("/api/v1/community/posts/media", files=photo, data={"accept_rules": "true", "challenge_id": later["id"]})
    assert early.status_code == 400

    # B enters with a photo and likes their own entry (doesn't count); C likes both, B likes A's
    client.cookies.clear()
    await register_and_login(client)
    b = dict(client.cookies)
    entry_b = (
        await client.post("/api/v1/community/posts/media", files=photo, data={"accept_rules": "true", "challenge_id": ch["id"]})
    ).json()
    await client.post(f"/api/v1/community/posts/{entry_b['id']}/like")
    await client.post(f"/api/v1/community/posts/{entry_a['id']}/like")
    client.cookies.clear()
    await register_and_login(client)
    await client.post(f"/api/v1/community/posts/{entry_a['id']}/like")
    await client.post(f"/api/v1/community/posts/{entry_b['id']}/like")

    page = (await client.get(f"/api/v1/community/challenges/{ch['id']}")).json()
    assert page["challenge"]["entries"] == 2 and [p["id"] for p in page["entries"]["posts"]] == [entry_a["id"], entry_b["id"]]

    # the admin ends it: A wins 1st (2 likes), B 2nd (1 like from someone else)
    await _as(client, admin_cookies)
    done = (await client.post(f"/api/v1/admin/community/challenges/{ch['id']}/finish")).json()
    assert done["state"] == "ended"
    assert [(w["place"], w["author"]["handle"], w["credits"], w["likes"]) for w in done["winners"]][0] == (1, a_handle, 50, 2)
    assert [w["place"] for w in done["winners"]] == [1, 2] and done["winners"][1]["credits"] == 30
    again_done = (await client.post(f"/api/v1/admin/community/challenges/{ch['id']}/finish")).json()
    assert len(again_done["winners"]) == 2  # paid once

    await _as(client, a)
    assert (await client.get("/api/v1/auth/me")).json()["credits_balance"] == a_credits + 50
    note = (await client.get("/api/v1/notifications")).json()["items"][0]
    assert note["kind"] == "challenge_win" and "1st place in Eid Look Week" in note["text"] and "50 free credits" in note["text"]
    assert note["url"] == f"/community/challenges/{ch['id']}"
    trophies = (await client.get(f"/api/v1/community/profiles/{a_handle}")).json()["trophies"]
    assert trophies == [{"challenge_id": ch["id"], "title": "Eid Look Week", "place": 1, "post_id": entry_a["id"]}]
    won = (await client.get(f"/api/v1/community/posts/{entry_a['id']}")).json()
    assert won["award"] == 1
    late = await client.post("/api/v1/community/posts/media", files=photo, data={"accept_rules": "true", "challenge_id": ch["id"]})
    assert late.status_code == 400  # closed
    await _as(client, b)
    assert (await client.get("/api/v1/notifications")).json()["items"][0]["kind"] == "challenge_win"  # 2nd place

    # a challenge whose time is up is finished by the background check
    await db.execute(update(Challenge).where(Challenge.id == later["id"]).values(starts_at=datetime.now(timezone.utc) - timedelta(days=9), ends_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    await db.commit()
    assert await challenge_service.finish_due(db) >= 1
    await _as(client, admin_cookies)
    finished = next(c for c in (await client.get("/api/v1/admin/community/challenges")).json() if c["id"] == later["id"])
    assert finished["state"] == "ended" and finished["winners"] == []  # nobody entered
    hidden = (await client.post(f"/api/v1/admin/community/challenges/{later['id']}/hidden", json={"hidden": True})).json()
    assert hidden["hidden"] is True
    await _as(client, b)
    assert later["id"] not in [c["id"] for c in (await client.get("/api/v1/community/challenges")).json()["ended"]]
    assert (await client.post("/api/v1/admin/community/challenges", json={"title": "Nope", "starts_at": _when(), "ends_at": _when(days=1)})).status_code == 403


async def test_every_member_hears_when_a_challenge_starts(client, db):  # noqa: ANN001
    member = await register_and_login(client)
    member_cookies = dict(client.cookies)
    del member
    client.cookies.clear()
    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    admin_cookies = dict(client.cookies)

    now_live = (
        await client.post(
            "/api/v1/admin/community/challenges",
            json={"title": "Wedding Guest Look", "starts_at": _when(minutes=-1), "ends_at": _when(days=7)},
        )
    ).json()
    later = (
        await client.post(
            "/api/v1/admin/community/challenges",
            json={"title": "Winter Layers", "starts_at": _when(days=8), "ends_at": _when(days=15)},
        )
    ).json()

    async def started_notes() -> list[dict]:
        items = (await client.get("/api/v1/notifications?limit=50")).json()["items"]
        return [n for n in items if n["kind"] == "challenge_started"]

    await _as(client, member_cookies)
    notes = await started_notes()
    assert [n["url"] for n in notes] == [f"/community/challenges/{now_live['id']}"]  # told at once; not yet about the later one
    assert "Wedding Guest Look" in notes[0]["text"] and "50 free credits" in notes[0]["text"]

    # the later one's start time comes: everyone is told, once
    await db.execute(update(Challenge).where(Challenge.id == later["id"]).values(starts_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    await db.commit()
    await challenge_service.announce_due(db)
    await challenge_service.announce_due(db)
    notes = await started_notes()
    assert [n["url"] for n in notes] == [f"/community/challenges/{later['id']}", f"/community/challenges/{now_live['id']}"]
    await _as(client, admin_cookies)
    assert len(await started_notes()) == 2  # the admin is a member too
