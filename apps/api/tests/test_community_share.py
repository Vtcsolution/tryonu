"""A shared community post's preview for LinkedIn, WhatsApp, Facebook…:
readable without signing in, only for posts anyone in the community may see."""

from __future__ import annotations

from app.models.community import CommunityPost
from tests.test_shared_looks import _finished_look


async def test_a_shared_post_shows_its_look_and_products_to_link_previews(client, db, monkeypatch):  # noqa: ANN001
    job_id, product = await _finished_look(client, db, monkeypatch)
    post = (
        await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "caption": "Eid look", "accept_rules": True})
    ).json()
    client.cookies.clear()  # LinkedIn's reader isn't signed in

    preview = await client.get(f"/api/v1/community/share/{post['id']}")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["caption"] == "Eid look" and body["has_photo"] and body["author_handle"]
    assert [p["name"] for p in body["products"]] == [product.name] and body["products"][0]["price"]

    photo = await client.get(f"/api/v1/community/share/{post['id']}/photo.jpg")
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg" and photo.content[:2] == b"\xff\xd8"

    row = await db.get(CommunityPost, post["id"])
    row.is_hidden = True
    await db.commit()
    assert (await client.get(f"/api/v1/community/share/{post['id']}")).status_code == 404  # hidden: nothing shown
    assert (await client.get(f"/api/v1/community/share/{post['id']}/photo.jpg")).status_code == 404
