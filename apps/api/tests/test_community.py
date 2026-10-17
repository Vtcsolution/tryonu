"""The community: members post looks, like, comment, follow, try a post's look,
report; admins hide content and block members. Members only."""

from __future__ import annotations

from tests.conftest import make_admin, register_and_login
from tests.test_shared_looks import _finished_look


async def _as(client, cookies: dict) -> None:  # noqa: ANN001
    client.cookies.clear()
    for name, value in cookies.items():
        client.cookies.set(name, value)


async def test_members_post_like_comment_follow_and_try_a_look(client, db, monkeypatch):  # noqa: ANN001
    job_id, product = await _finished_look(client, db, monkeypatch)  # member A's finished look
    a = dict(client.cookies)
    assert (await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "caption": "Eid look"})).status_code == 400  # rules first
    posted = await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "caption": "Eid look", "accept_rules": True})
    assert posted.status_code == 201, posted.text
    post = posted.json()
    assert post["is_mine"] and post["products"][0]["id"] == product.id and post["image_url"]
    assert (await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True})).status_code == 409
    a_handle = (await client.get("/api/v1/community/me")).json()["handle"]
    looks = (await client.get("/api/v1/community/my-looks")).json()  # what the Post a look picker shows
    assert [x["job_id"] for x in looks] == [job_id] and looks[0]["post_id"] == post["id"] and looks[0]["image_url"]
    assert (await client.get(f"/api/v1/community/posts/by-job/{job_id}")).json() == {"post_id": post["id"]}

    await client.post("/api/v1/auth/logout")
    client.cookies.clear()
    assert (await client.get("/api/v1/community/feed")).status_code == 401  # members only

    await register_and_login(client)  # member B
    b = dict(client.cookies)
    feed = (await client.get("/api/v1/community/feed")).json()["posts"]
    mine = next(p for p in feed if p["id"] == post["id"])
    assert mine["author"]["handle"] == a_handle and not mine["is_mine"] and not mine["liked_by_me"]

    assert (await client.post(f"/api/v1/community/posts/{post['id']}/like")).json() == {"liked": True, "like_count": 1}
    assert (await client.post(f"/api/v1/community/posts/{post['id']}/like")).json()["like_count"] == 1  # once
    top = (await client.post(f"/api/v1/community/posts/{post['id']}/comments", json={"body": "Love the colour!"})).json()
    reply = (await client.post(f"/api/v1/community/posts/{post['id']}/comments", json={"body": "Where is it from?", "parent_id": top["id"]})).json()
    assert reply["parent_id"] == top["id"]
    comments = (await client.get(f"/api/v1/community/posts/{post['id']}/comments")).json()
    assert [c["body"] for c in comments] == ["Love the colour!"] and comments[0]["replies"][0]["body"] == "Where is it from?"

    profile = (await client.post(f"/api/v1/community/profiles/{a_handle}/follow")).json()
    assert profile["followers"] == 1 and profile["followed_by_me"] and profile["posts"] == 1
    following = (await client.get("/api/v1/community/feed?tab=following")).json()["posts"]
    assert [p["id"] for p in following] == [post["id"]] and following[0]["following_author"]

    tried = (await client.post(f"/api/v1/community/posts/{post['id']}/try")).json()
    assert tried["product_id"] == product.id or tried["outfit_id"]

    # A sees the counts, and as the post's owner can remove a comment on it
    await _as(client, a)
    again = (await client.get(f"/api/v1/community/posts/{post['id']}")).json()
    assert (again["like_count"], again["comment_count"]) == (1, 2)
    assert (await client.delete(f"/api/v1/community/comments/{reply['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/community/posts/{post['id']}")).json()["comment_count"] == 1

    # usernames: valid, unique
    assert (await client.patch("/api/v1/community/me", json={"handle": "a!"})).status_code == 400
    await _as(client, b)
    b_handle = (await client.get("/api/v1/community/me")).json()["handle"]
    await _as(client, a)
    assert (await client.patch("/api/v1/community/me", json={"handle": b_handle})).status_code == 409
    assert (await client.patch("/api/v1/community/me", json={"handle": "zia.style", "bio": "Bridal looks"})).json()["handle"] == "zia.style"


async def test_reports_hide_content_and_bans_stop_posting(client, db, monkeypatch):  # noqa: ANN001
    job_id, _ = await _finished_look(client, db, monkeypatch)
    a = dict(client.cookies)
    post = (await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True})).json()

    await register_and_login(client)
    assert (await client.post("/api/v1/community/reports", json={"post_id": post["id"], "reason": "Not a real photo"})).status_code == 201

    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    reports = (await client.get("/api/v1/admin/community/reports")).json()
    r = next(x for x in reports if x["target_id"] == post["id"])
    assert r["kind"] == "post" and r["image_url"]
    assert (await client.post(f"/api/v1/admin/community/reports/{r['id']}/resolve", json={"action": "ban"})).status_code == 200
    assert all(p["id"] != post["id"] for p in (await client.get("/api/v1/community/feed")).json()["posts"])

    await _as(client, a)  # the blocked member can't post or comment
    assert (await client.post(f"/api/v1/community/posts/{post['id']}/comments", json={"body": "hi"})).status_code == 403
