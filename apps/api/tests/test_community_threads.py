"""Community conversations: replies to replies, likes on comments, photos and
looks in comments, outside links taken out (TryOnU links kept, with a
preview), the faces of who liked a post, and the admin's view of everything
members do."""

from __future__ import annotations

from app.services.community_links import clean_text
from tests.conftest import make_admin, register_and_login, small_jpeg_bytes
from tests.test_community import _as
from tests.test_shared_looks import _finished_look


def test_only_tryonu_links_stay():
    text, removed = clean_text(
        "Love it! Buy at https://cheap-dresses.com/sale or www.myshop.pk, bit.ly/xyz, mail me@gmail.com. "
        "Same one: https://tryonu.app/stores/zia-boutique and tryonu.app/try?product=abc"
    )
    assert removed == 4
    assert "cheap-dresses" not in text and "myshop" not in text and "bit.ly" not in text and "gmail" not in text
    assert "https://tryonu.app/stores/zia-boutique" in text and "tryonu.app/try?product=abc" in text
    # ordinary words are left alone
    assert clean_text("Size M.Thanks e.g. this @anna.pk ok")[1] == 0
    assert clean_text("Shop link: https://api.tryonu.app/api/v1/affiliate/go/123")[1] == 0
    assert clean_text("https://api.tryonu.app/api/v1/auth/me")[1] == 1


async def test_threads_likes_photos_looks_and_links_in_comments(client, db, monkeypatch):  # noqa: ANN001
    job_id, product = await _finished_look(client, db, monkeypatch)  # member A
    a = dict(client.cookies)
    post = (await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True, "caption": "Eid! www.spam.com"})).json()
    assert post["caption"] == "Eid!" and post["links_removed"] == 1  # outside links never show
    a_handle = (await client.get("/api/v1/community/me")).json()["handle"]

    await register_and_login(client)  # member B
    b = dict(client.cookies)
    b_handle = (await client.get("/api/v1/community/me")).json()["handle"]
    url = f"/api/v1/community/posts/{post['id']}/comments"

    # a comment with an outside link and a TryOnU product link: the outside one goes, the product shows as a card
    top = await client.post(url, json={"body": f"Get it cheaper at https://other.shop/x — or here https://tryonu.app/try?product={product.id}"})
    assert top.status_code == 201, top.text
    top = top.json()
    assert top["links_removed"] == 1 and "other.shop" not in top["body"]
    assert top["previews"][0]["kind"] == "product" and top["previews"][0]["title"] == product.name
    only_link = await client.post(url, json={"body": "https://other.shop/x"})
    assert only_link.status_code == 400 and "TryOnU" in only_link.json()["detail"]
    assert (await client.post(url, json={"body": "  "})).status_code == 400

    # a photo in a comment: uploaded first, then posted; nobody can use another member's photo
    up = await client.post("/api/v1/community/comment-images", files={"file": ("p.jpg", small_jpeg_bytes(), "image/jpeg")})
    assert up.status_code == 200, up.text
    key = up.json()["image_key"]
    with_photo = (await client.post(url, json={"body": "", "image_key": key, "parent_id": top["id"]})).json()
    assert with_photo["image_url"] and with_photo["reply_to"] == b_handle and with_photo["parent_id"] == top["id"]

    # A answers the reply, and B answers again: replies to replies, as deep as people go
    await _as(client, a)
    assert (await client.post(url, json={"body": "mine", "image_key": key})).status_code == 400  # B's photo
    deeper = (await client.post(url, json={"body": "Thank you!", "parent_id": with_photo["id"], "tryon_job_id": job_id})).json()
    assert deeper["parent_id"] == with_photo["id"] and deeper["reply_to"] == b_handle and deeper["look"]["image_url"]
    assert deeper["look"]["products"][0]["id"] == product.id
    await _as(client, b)
    assert (await client.post(url, json={"body": "mine too", "tryon_job_id": job_id})).status_code == 404  # A's look
    deepest = (await client.post(url, json={"body": "Lovely", "parent_id": deeper["id"]})).json()
    assert deepest["reply_to"] == a_handle

    tree = (await client.get(url)).json()
    assert [c["id"] for c in tree] == [top["id"]]
    level2 = tree[0]["replies"][0]
    level3 = level2["replies"][0]
    assert level2["id"] == with_photo["id"] and level3["id"] == deeper["id"] and level3["replies"][0]["id"] == deepest["id"]

    # likes on comments; trying the look someone added to a comment
    liked = await client.post(f"/api/v1/community/comments/{deeper['id']}/like")
    assert liked.json() == {"liked": True, "like_count": 1}
    assert (await client.post(f"/api/v1/community/comments/{deeper['id']}/like")).json()["like_count"] == 1  # once
    tree = (await client.get(url)).json()
    assert tree[0]["replies"][0]["replies"][0]["liked_by_me"] is True
    tried = (await client.post(f"/api/v1/community/comments/{deeper['id']}/try")).json()
    assert tried["product_id"] == product.id or tried["outfit_id"]
    assert (await client.delete(f"/api/v1/community/comments/{deeper['id']}/like")).json() == {"liked": False, "like_count": 0}

    # the small faces of who liked the post
    await client.post(f"/api/v1/community/posts/{post['id']}/like")
    seen = (await client.get(f"/api/v1/community/posts/{post['id']}")).json()
    assert [x["handle"] for x in seen["likers"]] == [b_handle] and seen["comment_count"] == 4
    assert [x["handle"] for x in (await client.get(f"/api/v1/community/posts/{post['id']}/likes")).json()] == [b_handle]

    # deleting a reply removes everything under it
    assert (await client.delete(f"/api/v1/community/comments/{with_photo['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/community/posts/{post['id']}")).json()["comment_count"] == 1
    assert (await client.get(url)).json()[0]["replies"] == []

    # the admin sees every member, what they did, and every comment
    admin = await register_and_login(client)
    await make_admin(db, admin["user"]["id"])
    stats = (await client.get("/api/v1/admin/community/stats")).json()  # (other tests share the database)
    assert stats["posts"] >= 1 and stats["comments"] >= 1 and stats["likes"] >= 1 and stats["links_removed"] >= 2
    rows = {}
    for handle in (a_handle, b_handle):
        found = (await client.get(f"/api/v1/admin/community/members?q={handle}")).json()["rows"]
        rows[handle] = next(r for r in found if r["handle"] == handle)
    assert rows[b_handle]["comments"] == 1 and rows[b_handle]["likes_given"] == 1 and rows[b_handle]["links_removed"] == 1
    assert rows[a_handle]["posts"] == 1 and rows[a_handle]["likes_received"] == 1 and rows[a_handle]["links_removed"] == 1
    engaged = (await client.get("/api/v1/admin/community/members?sort=engaged")).json()
    scores = [r["posts"] * 3 + r["comments"] * 2 + r["likes_given"] + r["likes_received"] for r in engaged["rows"]]
    assert scores == sorted(scores, reverse=True)  # the most engaged first

    comments = (await client.get(f"/api/v1/admin/community/comments?member={b_handle}")).json()
    assert comments["total"] == 1 and comments["rows"][0]["links_removed"] == 1 and comments["rows"][0]["post_author_handle"] == a_handle
    cid = comments["rows"][0]["id"]
    assert (await client.post(f"/api/v1/admin/community/comments/{cid}/hidden", json={"hidden": True})).json() == {"hidden": True}
    assert (await client.get(f"/api/v1/community/posts/{post['id']}")).json()["comment_count"] == 0
    assert cid in [c["id"] for c in (await client.get("/api/v1/admin/community/comments?show=hidden")).json()["rows"]]

    posts = (await client.get(f"/api/v1/admin/community/posts?member={a_handle}")).json()
    assert posts["rows"][0]["id"] == post["id"] and posts["rows"][0]["image_url"] and posts["rows"][0]["links_removed"] == 1
    assert (await client.post(f"/api/v1/admin/community/posts/{post['id']}/hidden", json={"hidden": True})).status_code == 200
    assert (await client.post(f"/api/v1/admin/community/users/{rows[b_handle]['user_id']}/ban")).status_code == 200
    await _as(client, b)
    assert (await client.post("/api/v1/community/comment-images", files={"file": ("p.jpg", small_jpeg_bytes(), "image/jpeg")})).status_code == 403

    # members can't use the admin views
    assert (await client.get("/api/v1/admin/community/members")).status_code == 403


async def test_members_bookmark_posts(client, db, monkeypatch):  # noqa: ANN001
    job_id, _ = await _finished_look(client, db, monkeypatch)
    post = (await client.post("/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True})).json()
    client.cookies.clear()
    await register_and_login(client)
    assert (await client.post(f"/api/v1/community/posts/{post['id']}/save")).json() == {"saved": True}
    assert (await client.post(f"/api/v1/community/posts/{post['id']}/save")).json() == {"saved": True}  # once
    assert (await client.get(f"/api/v1/community/posts/{post['id']}")).json()["saved_by_me"] is True
    saved = (await client.get("/api/v1/community/saved")).json()["posts"]
    assert [p["id"] for p in saved] == [post["id"]]
    assert (await client.delete(f"/api/v1/community/posts/{post['id']}/save")).json() == {"saved": False}
    assert (await client.get("/api/v1/community/saved")).json()["posts"] == []
