"""A post with several photos, swiped through, and the people-to-follow list."""

from __future__ import annotations

from tests.conftest import register_and_login, small_jpeg_bytes


def _photos(n: int) -> list[tuple[str, tuple[str, bytes, str]]]:
    files = [("file", ("1.jpg", small_jpeg_bytes(), "image/jpeg"))]
    files += [("more", (f"{i}.jpg", small_jpeg_bytes(), "image/jpeg")) for i in range(2, n + 1)]
    return files


async def test_a_member_posts_several_photos_in_one_post(client):
    await register_and_login(client)
    resp = await client.post("/api/v1/community/posts/media", files=_photos(4), data={"caption": "Four looks", "accept_rules": "true"})
    assert resp.status_code == 201, resp.text
    post = resp.json()
    assert post["media_kind"] == "image" and len(post["images"]) == 4
    assert post["images"][0] == post["image_url"]
    again = (await client.get(f"/api/v1/community/posts/{post['id']}")).json()
    assert len(again["images"]) == 4


async def test_one_photo_has_no_photo_list_and_ten_is_the_most(client):
    await register_and_login(client)
    one = (await client.post("/api/v1/community/posts/media", files=_photos(1), data={"accept_rules": "true"})).json()
    assert one["images"] == []
    too_many = await client.post("/api/v1/community/posts/media", files=_photos(11), data={"accept_rules": "true"})
    assert too_many.status_code == 400 and "10 photos" in too_many.json()["detail"]


async def test_people_to_follow_are_active_members_i_dont_follow_yet(client):
    poster = await register_and_login(client)
    await client.post("/api/v1/community/posts/media", files=_photos(1), data={"accept_rules": "true"})
    client.cookies.clear()
    await register_and_login(client)
    people = (await client.get("/api/v1/community/people/suggested?limit=24")).json()
    names = {p["handle"] for p in people}
    poster_handle = next((p["handle"] for p in people if p["posts"] >= 1), None)
    assert poster_handle is not None and all(p["posts"] >= 1 for p in people)
    await client.post(f"/api/v1/community/profiles/{poster_handle}/follow")
    after = {p["handle"] for p in (await client.get("/api/v1/community/people/suggested?limit=24")).json()}
    assert poster_handle in names and poster_handle not in after
    assert poster  # the poster signed up
