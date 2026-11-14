"""TryOnU team members like and comment as the team's profiles, which always
carry the "TryOnU team" badge; ordinary members can't act as anyone else."""

from __future__ import annotations

from sqlalchemy import update

from app.models.user import User
from tests.conftest import register_and_login, small_jpeg_bytes


async def _a_post(client) -> str:  # noqa: ANN001
    post = await client.post(
        "/api/v1/community/posts/media", files={"file": ("a.jpg", small_jpeg_bytes(), "image/jpeg")}, data={"accept_rules": "true"}
    )
    return post.json()["id"]


async def test_a_team_member_comments_and_likes_as_a_team_profile_with_the_badge(client, db):
    me = await register_and_login(client)
    await db.execute(update(User).where(User.id == me["user"]["id"]).values(is_team=True))
    await db.commit()
    person = await client.post(
        "/api/v1/team/people",
        data={"name": "Sara Stylist", "handle": "sara_stylist_t1"},
        files={"photo": ("sara.jpg", small_jpeg_bytes(), "image/jpeg")},
    )
    assert person.status_code in (200, 201), person.text
    pid = person.json()["id"]
    post_id = await _a_post(client)

    c = await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"body": "Love this coat!", "person_id": pid})
    assert c.status_code in (200, 201), c.text
    assert c.json()["author"]["handle"] == "sara_stylist_t1" and c.json()["author"]["team"] is True

    liked = await client.post(f"/api/v1/community/posts/{post_id}/like?as_person={pid}")
    assert liked.json()["like_count"] == 1
    reply = await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"body": "Thanks!", "parent_id": c.json()["id"]})
    assert reply.json()["author"]["team"] is True  # a team member's own account is team too
    profile = (await client.get("/api/v1/community/profiles/sara_stylist_t1")).json()
    assert profile["team"] is True


async def test_ordinary_members_cannot_act_as_someone_else(client):
    await register_and_login(client)
    post_id = await _a_post(client)
    refused = await client.post(f"/api/v1/community/posts/{post_id}/like?as_person=anyone")
    assert refused.status_code == 403
    mine = (await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"body": "My own"})).json()
    assert mine["author"]["team"] is False
