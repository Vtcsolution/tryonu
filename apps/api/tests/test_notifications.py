"""Notifications: the bell (likes, comments, replies, follows), reading them,
phone notifications sent once the change is saved, and the daily email with
its one-click unsubscribe."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.config import get_settings
from app.models.notification import Notification
from app.services import notification_service as svc
from tests.conftest import register_and_login
from tests.test_community import _as
from tests.test_shared_looks import _finished_look


async def _two_members_and_a_post(client, db, monkeypatch):  # noqa: ANN001, ANN202
    job_id, _ = await _finished_look(client, db, monkeypatch)  # member A
    a = dict(client.cookies)
    post = (await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True})).json()
    a_handle = (await client.get("/api/v1/community/me")).json()["handle"]
    await register_and_login(client)  # member B
    b = dict(client.cookies)
    b_handle = (await client.get("/api/v1/community/me")).json()["handle"]
    return a, b, post, a_handle, b_handle


async def test_the_bell_tells_members_what_happened(client, db, monkeypatch):  # noqa: ANN001
    a, b, post, a_handle, b_handle = await _two_members_and_a_post(client, db, monkeypatch)
    pid = post["id"]

    # B likes (twice, with an unlike between: A hears once), comments and follows
    await client.post(f"/api/v1/community/posts/{pid}/like")
    await client.delete(f"/api/v1/community/posts/{pid}/like")
    await client.post(f"/api/v1/community/posts/{pid}/like")
    comment = (await client.post(f"/api/v1/community/posts/{pid}/comments", json={"body": "Love   the colour of this dress!"})).json()
    await client.post(f"/api/v1/community/profiles/{a_handle}/follow")
    assert (await client.get("/api/v1/notifications/unread-count")).json() == {"unread": 0}  # nothing for B yet

    await _as(client, a)
    assert (await client.get("/api/v1/notifications/unread-count")).json() == {"unread": 3}
    page = (await client.get("/api/v1/notifications")).json()
    assert page["unread"] == 3
    kinds = [n["kind"] for n in page["items"]]
    assert kinds == ["follow", "comment", "post_like"]  # newest first
    follow, said, liked = page["items"]
    assert follow["url"] == f"/u/{b_handle}" and follow["actor"]["handle"] == b_handle
    assert "commented on your post" in said["text"] and "Love the colour of this dress!" in said["text"]
    assert liked["url"] == f"/community/post/{pid}" and liked["image_url"] and not liked["read"]

    # A replies to B and likes B's comment: B hears about both; A liking their own post tells nobody
    await client.post(f"/api/v1/community/posts/{pid}/comments", json={"body": "Thank you!", "parent_id": comment["id"]})
    await client.post(f"/api/v1/community/comments/{comment['id']}/like")
    await client.post(f"/api/v1/community/posts/{pid}/like")
    assert (await client.post(f"/api/v1/notifications/{liked['id']}/read")).json() == {"unread": 2}
    assert (await client.post("/api/v1/notifications/read-all")).json() == {"unread": 0}
    assert all(n["read"] for n in (await client.get("/api/v1/notifications")).json()["items"])

    await _as(client, b)
    items = (await client.get("/api/v1/notifications")).json()["items"]
    assert [n["kind"] for n in items] == ["comment_like", "reply"]
    assert "replied to your comment" in items[1]["text"] and "Thank you!" in items[1]["text"]
    assert (await client.post(f"/api/v1/notifications/{liked['id']}/read")).status_code == 404  # A's, not B's


async def test_phone_notifications_go_out_once_saved(client, db, monkeypatch):  # noqa: ANN001
    a, b, post, _, _ = await _two_members_and_a_post(client, db, monkeypatch)
    await _as(client, a)
    settings = (await client.get("/api/v1/notifications/settings")).json()
    assert settings == {"email": True, "push_key": None, "phones": 0}  # no keys on this server yet
    sub = {"endpoint": "https://push.example.com/send/abc123", "keys": {"p256dh": "BPublicKeyOfThePhone-xyz", "auth": "authsecret1"}}
    assert (await client.post("/api/v1/notifications/push", json=sub)).status_code == 400

    from app.scripts.vapid_keys import make_keys

    public, private = make_keys()
    monkeypatch.setattr(get_settings(), "VAPID_PUBLIC_KEY", public)
    monkeypatch.setattr(get_settings(), "VAPID_PRIVATE_KEY", private)
    sent: list = []

    def fake_send(push):  # noqa: ANN001, ANN202
        sent.append(push)
        return 410 if "gone" in push.endpoint else 0

    monkeypatch.setattr(svc, "_send_one", fake_send)
    on = (await client.post("/api/v1/notifications/push", json=sub)).json()
    assert on["push_key"] == public and on["phones"] == 1
    await client.post("/api/v1/notifications/push", json={**sub, "endpoint": "https://push.example.com/send/gone"})

    await _as(client, b)
    await client.post(f"/api/v1/community/posts/{post['id']}/like")
    await asyncio.gather(*list(svc._TASKS))  # sent right after the like was saved
    assert len(sent) == 2 and '"liked your post"' not in sent[0].payload and "liked your post" in sent[0].payload
    assert f"/community/post/{post['id']}" in sent[0].payload

    await _as(client, a)
    assert (await client.get("/api/v1/notifications/settings")).json()["phones"] == 1  # the phone that's gone was removed
    assert (await client.post("/api/v1/notifications/push/remove", json={"endpoint": sub["endpoint"]})).json()["phones"] == 0


async def test_the_daily_email_and_its_unsubscribe_link(client, db, monkeypatch):  # noqa: ANN001
    from app.email.registry import get_email_provider

    a, b, post, a_handle, _ = await _two_members_and_a_post(client, db, monkeypatch)
    await client.post(f"/api/v1/community/posts/{post['id']}/like")
    await client.post(f"/api/v1/community/profiles/{a_handle}/follow")
    await _as(client, a)
    a_email = (await client.get("/api/v1/auth/me")).json()["email"]
    outbox = get_email_provider().sent

    def to_a(start: int) -> list[dict]:
        return [m for m in outbox[start:] if m["to"] == a_email]

    before = len(outbox)
    await svc.send_digests(db)
    assert to_a(before) == []  # too new: the bell and phone get the first chance
    await db.execute(update(Notification).values(created_at=datetime.now(timezone.utc) - timedelta(hours=2)))
    await db.commit()

    before = len(outbox)
    await svc.send_digests(db)
    mine = to_a(before)
    assert len(mine) == 1 and mine[0]["subject"] == "You have 2 new notifications on TryOnU"
    body = mine[0]["body"]
    assert "liked your post" in body and "started following you" in body and "/notifications" in body
    before = len(outbox)
    await svc.send_digests(db)
    assert to_a(before) == []  # once a day at most

    link = body.split("Turn them off here: ")[1].split()[0]
    path = link[link.index("/api/"):]
    assert (await client.get(path.replace("&t=", "&t=x"))).status_code == 400  # a wrong link does nothing
    page = await client.get(path)
    assert page.status_code == 200 and "no more daily emails" in page.text
    assert (await client.get("/api/v1/notifications/settings")).json()["email"] is False
    assert (await client.patch("/api/v1/notifications/settings", json={"email": True})).json()["email"] is True


async def test_mentions_tell_people_and_suggest_names(client, db, monkeypatch):  # noqa: ANN001
    a, b, post, a_handle, b_handle = await _two_members_and_a_post(client, db, monkeypatch)
    client.cookies.clear()
    await register_and_login(client)  # member C
    c = dict(client.cookies)
    c_handle = (await client.get("/api/v1/community/me")).json()["handle"]
    await client.post(f"/api/v1/community/profiles/{b_handle}/follow")

    # suggestions: who I follow first; matching by the start of the @username
    people = (await client.get(f"/api/v1/community/people?q={b_handle[:4]}")).json()
    assert people[0]["handle"] == b_handle
    assert c_handle not in [p["handle"] for p in (await client.get("/api/v1/community/people")).json()]  # never myself

    # C comments on A's post naming B (and A, who hears about the comment anyway, and someone who doesn't exist)
    url = f"/api/v1/community/posts/{post['id']}/comments"
    await client.post(url, json={"body": f"@{b_handle} you need this! @{a_handle} where from? @nobody_here_123"})
    await _as(client, b)
    note = (await client.get("/api/v1/notifications")).json()["items"][0]
    assert note["kind"] == "mention" and "mentioned you" in note["text"] and note["url"] == f"/community/post/{post['id']}"
    await _as(client, a)
    kinds = [n["kind"] for n in (await client.get("/api/v1/notifications")).json()["items"]]
    assert kinds.count("comment") == 1 and "mention" not in kinds  # told once, as the post's owner
    await _as(client, c)
    assert all(n["kind"] != "mention" for n in (await client.get("/api/v1/notifications")).json()["items"])
