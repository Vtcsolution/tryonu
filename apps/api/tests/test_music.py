"""The free music library: admins add songs, members put one on a post, and
it comes back with the post (for Reels). Offline."""

from __future__ import annotations

from sqlalchemy import delete

from app.models.community import MusicTrack
from tests.conftest import make_admin, register_and_login, small_jpeg_bytes
from tests.test_community import _as

MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 2048


async def test_admins_add_songs_and_members_put_one_on_a_post(client, db):  # noqa: ANN001
    await db.execute(delete(MusicTrack))
    await db.commit()
    await register_and_login(client)
    member = dict(client.cookies)
    song = {"file": ("happy.mp3", MP3, "audio/mpeg")}
    assert (await client.post("/api/v1/admin/community/music", files=song, data={"title": "x"})).status_code == 403

    client.cookies.clear()
    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    not_audio = await client.post(
        "/api/v1/admin/community/music", files={"file": ("a.mp3", small_jpeg_bytes(), "audio/mpeg")}, data={"title": "Fake"}
    )
    assert not_audio.status_code == 400
    added = await client.post("/api/v1/admin/community/music", files=song, data={"title": "Sunny Day", "artist": "TryOnU", "mood": "Happy"})
    assert added.status_code == 201, added.text
    track = added.json()
    assert track["mood"] == "happy" and track["is_active"] and track["url"] and track["uses"] == 0
    off = (
        await client.post("/api/v1/admin/community/music", files=song, data={"title": "Old Song"})
    ).json()
    await client.patch(f"/api/v1/admin/community/music/{off['id']}", json={"is_active": False})

    await _as(client, member)
    library = (await client.get("/api/v1/community/music")).json()
    assert [t["title"] for t in library] == ["Sunny Day"]  # turned-off songs aren't offered

    def post(track_id: str):  # noqa: ANN202
        return client.post(
            "/api/v1/community/posts/media",
            files={"file": ("me.jpg", small_jpeg_bytes((800, 1000)), "image/jpeg")},
            data={"caption": "With music", "accept_rules": "true", "music_track_id": track_id},
        )

    assert (await post(off["id"])).status_code == 400
    made = await post(track["id"])
    assert made.status_code == 201, made.text
    music = made.json()["music"]
    assert music["title"] == "Sunny Day" and music["artist"] == "TryOnU" and music["url"]
    reels = (await client.get("/api/v1/community/feed?tab=for_you")).json()["posts"]
    assert next(p for p in reels if p["id"] == made.json()["id"])["music"]["id"] == track["id"]

    # deleting a song takes it off the posts that used it
    await _as(client, {})
    client.cookies.clear()
    await register_and_login(client)
    await make_admin(db, (await client.get("/api/v1/auth/me")).json()["id"])
    listed = (await client.get("/api/v1/admin/community/music")).json()
    assert next(t for t in listed if t["id"] == track["id"])["uses"] == 1
    assert (await client.delete(f"/api/v1/admin/community/music/{track['id']}")).status_code == 204
    after = (await client.get(f"/api/v1/community/posts/{made.json()['id']}")).json()
    assert after["music"] is None
