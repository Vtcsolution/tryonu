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


async def test_a_member_uploads_changes_and_removes_a_profile_picture(client):  # noqa: ANN001
    from tests.conftest import small_jpeg_bytes

    await register_and_login(client)
    assert (await client.post("/api/v1/community/me/avatar", files={"file": ("x.txt", b"not a photo", "text/plain")})).status_code == 400
    up = await client.post("/api/v1/community/me/avatar", files={"file": ("me.jpg", small_jpeg_bytes((900, 1200)), "image/jpeg")})
    assert up.status_code == 200, up.text
    url = up.json()["avatar_url"]
    assert url.startswith("/api/v1/community/avatar/")
    img = await client.get(url)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    from io import BytesIO

    from PIL import Image

    assert Image.open(BytesIO(img.content)).size == (400, 400)  # a neat square

    again = (await client.post("/api/v1/community/me/avatar", files={"file": ("me2.jpg", small_jpeg_bytes((600, 600)), "image/jpeg")})).json()
    assert again["avatar_url"] != url and (await client.get(url)).status_code == 404  # the old one is gone
    assert (await client.delete("/api/v1/community/me/avatar")).json()["avatar_url"] is None


# ------------------------------------------------------------------ members' own photos and videos


def _post_media(client, name, data, ctype, caption="My look"):  # noqa: ANN001, ANN202
    return client.post(
        "/api/v1/community/posts/media",
        files={"file": (name, data, ctype)},
        data={"caption": caption, "accept_rules": "true"},
    )


async def test_a_member_posts_a_photo_and_a_video(client, monkeypatch):  # noqa: ANN001
    from tests.conftest import small_jpeg_bytes

    await register_and_login(client)
    refused = await client.post("/api/v1/community/posts/media", files={"file": ("a.jpg", small_jpeg_bytes(), "image/jpeg")}, data={"accept_rules": "false"})
    assert refused.status_code == 400  # rules first
    photo = await _post_media(client, "me.jpg", small_jpeg_bytes((800, 1000)), "image/jpeg")
    assert photo.status_code == 201, photo.text
    assert photo.json()["media_kind"] == "image" and photo.json()["image_url"] and photo.json()["products"] == []
    assert (await client.post(f"/api/v1/community/posts/{photo.json()['id']}/try")).status_code == 400  # nothing to try on

    # a server without ffmpeg keeps the video as uploaded
    monkeypatch.setattr("app.services.community_media.shutil.which", lambda name: None)
    fake_mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 2000
    video = await _post_media(client, "clip.mp4", fake_mp4, "video/mp4")
    assert video.status_code == 201, video.text
    assert video.json()["media_kind"] == "video" and video.json()["video_url"] and video.json()["image_url"] is None
    assert (await _post_media(client, "notes.txt", b"just text, not media", "text/plain")).status_code in (400, 415)

    feed = (await client.get("/api/v1/community/feed")).json()["posts"]
    kinds = {p["id"]: p["media_kind"] for p in feed}
    assert kinds[photo.json()["id"]] == "image" and kinds[video.json()["id"]] == "video"
    assert (await client.delete(f"/api/v1/community/posts/{video.json()['id']}")).status_code == 204


async def test_videos_are_converted_with_a_cover_picture_when_ffmpeg_is_installed(client, tmp_path):  # noqa: ANN001
    import shutil
    import subprocess

    import pytest

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg isn't installed here")
    clip = tmp_path / "clip.mov"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=24", "-t", "2", "-pix_fmt", "yuv420p", str(clip)],
        check=True, timeout=120,
    )
    await register_and_login(client)
    posted = await _post_media(client, "clip.mov", clip.read_bytes(), "video/quicktime")
    assert posted.status_code == 201, posted.text
    body = posted.json()
    assert body["media_kind"] == "video" and ".mp4" in body["video_url"] and body["poster_url"]
    assert (await client.get(body["video_url"])).headers["content-type"] == "video/mp4"
