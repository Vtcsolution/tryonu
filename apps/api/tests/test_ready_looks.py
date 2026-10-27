"""Ready looks: a team member publishes a finished try-on; shoppers see it on
tryonu.app/looks with its outfit-receipt picture and try it on themselves."""

from __future__ import annotations

from app.models.user import User
from tests.conftest import register_and_login, small_jpeg_bytes
from tests.test_shared_looks import _finished_look


async def _team(db, user_id: str) -> None:  # noqa: ANN001
    user = await db.get(User, user_id)
    user.is_team = True
    await db.commit()


async def test_a_team_member_publishes_a_look_and_shoppers_try_it(client, db, monkeypatch):  # noqa: ANN001
    async def no_network(url: str) -> bytes:  # noqa: ARG001 - product photos without the internet
        return small_jpeg_bytes()

    monkeypatch.setattr("app.services.tryon_direct.inputs.fetch_product_image", no_network)
    job_id, product = await _finished_look(client, db, monkeypatch)
    me = (await client.get("/api/v1/auth/me")).json()

    # a member who isn't on the team can't publish
    refused = await client.post("/api/v1/team/looks", json={"tryon_job_id": job_id, "title": "Bridal look"})
    assert refused.status_code == 403

    await _team(db, me["id"])
    made = await client.post("/api/v1/team/looks", json={"tryon_job_id": job_id, "title": "Pink bridal look", "audience": "women"})
    assert made.status_code == 201, made.text
    look = made.json()
    assert look["title"] == "Pink bridal look" and [i["product_id"] for i in look["items"]] == [product.id]
    assert [t["item"] for t in look["layout"]["tiles"]] == [0]
    assert "/affiliate/go/" in look["items"][0]["buy_url"]
    assert look["mine"] is True and look["tryon_job_id"] == job_id and look["created_at"]

    # the team panel lists it as theirs
    panel = (await client.get("/api/v1/team/looks")).json()
    assert [x["mine"] for x in panel if x["id"] == look["id"]] == [True]

    # anyone sees it on the page, with its pictures
    await client.post("/api/v1/auth/logout")
    listed = (await client.get("/api/v1/looks", params={"audience": "women"})).json()
    assert look["id"] in [x["id"] for x in listed]
    assert all(x["tryon_job_id"] is None and x["mine"] is False for x in listed)
    for url in (look["card_url"], look["card_small_url"], look["image_url"]):
        path = url.split("/api/v1/", 1)[1]
        pic = await client.get(f"/api/v1/{path}")
        assert pic.status_code == 200 and pic.headers["content-type"] == "image/jpeg" and pic.content

    # a shopper tries it on: the products become theirs, ready on the try-on page
    await register_and_login(client)
    tried = (await client.post(f"/api/v1/looks/{look['id']}/try")).json()
    assert tried["product_id"] == product.id or tried["outfit_id"]

    # the team hides it, then deletes it
    await client.post("/api/v1/auth/logout")
    await client.post("/api/v1/auth/login", json={"email": me["email"], "password": "password123"})
    hidden = (await client.patch(f"/api/v1/team/looks/{look['id']}", json={"is_published": False})).json()
    assert hidden["is_published"] is False
    assert look["id"] not in [x["id"] for x in (await client.get("/api/v1/looks")).json()]
    assert (await client.delete(f"/api/v1/team/looks/{look['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/looks/{look['id']}")).status_code == 404


async def test_the_outfit_receipt_picture_is_a_post_sized_jpeg():
    import io

    from PIL import Image

    from app.services.ready_look_card import CardItem, render_card

    person = Image.new("RGB", (768, 1024), (220, 220, 222))
    Image.Image.paste(person, (40, 40, 40), (300, 200, 470, 900))  # a dark figure on a light backdrop
    buf = io.BytesIO()
    person.save(buf, "JPEG")
    card, layout = render_card(
        "Men's winter look",
        buf.getvalue(),
        [CardItem("Wool overcoat", "$120.00", small_jpeg_bytes()), CardItem("Ribbed wool scarf", "£225.00", None),
         CardItem("Chelsea boots", "$175.46", small_jpeg_bytes(), (0.4, 0.9, 0.6, 0.98))],
    )
    img = Image.open(io.BytesIO(card))
    assert img.size == (1080, 1350) and img.format == "JPEG"
    # each product gets a numbered card with a short name, inside the frame
    assert sorted(t["n"] for t in layout["tiles"]) == [1, 2, 3]
    assert {t["label"] for t in layout["tiles"]} == {"Coat", "Scarf", "Boots"}
    for t in layout["tiles"]:
        x, y, w, h = t["box"]
        assert 0 <= x and x + w <= 1080 and 0 <= y and y + h <= 1350 - layout["band"]


async def test_the_team_posts_a_look_to_the_community_as_a_person(client, db, monkeypatch):  # noqa: ANN001
    async def no_network(url: str) -> bytes:  # noqa: ARG001
        return small_jpeg_bytes()

    monkeypatch.setattr("app.services.tryon_direct.inputs.fetch_product_image", no_network)
    job_id, product = await _finished_look(client, db, monkeypatch)
    me = (await client.get("/api/v1/auth/me")).json()
    photo = {"photo": ("haseeb.jpg", small_jpeg_bytes(), "image/jpeg")}

    # only the team can add people
    assert (await client.post("/api/v1/team/people", data={"name": "Haseeb", "handle": "haseeb"}, files=photo)).status_code == 403
    await _team(db, me["id"])

    made = await client.post("/api/v1/team/people", data={"name": "Haseeb", "handle": "@Haseeb"}, files=photo)
    assert made.status_code == 201, made.text
    person = made.json()
    assert person["handle"] == "haseeb" and person["avatar_url"] and person["posts"] == 0
    taken = await client.post("/api/v1/team/people", data={"name": "Other", "handle": "haseeb"}, files=photo)
    assert taken.status_code == 409

    look = (await client.post("/api/v1/team/looks", json={"tryon_job_id": job_id, "title": "Men's white shirt look", "audience": "men"})).json()
    posted = await client.post(
        f"/api/v1/team/looks/{look['id']}/community",
        json={"person_id": person["id"], "caption": "Tried it on before buying it.", "poll": True},
    )
    assert posted.status_code == 201, posted.text
    post_id = posted.json()["post_id"]
    again = await client.post(f"/api/v1/team/looks/{look['id']}/community", json={"person_id": person["id"]})
    assert again.status_code == 409

    # on the feed it's Haseeb's post: the try-on picture with the products
    post = (await client.get(f"/api/v1/community/posts/{post_id}")).json()
    assert post["author"]["handle"] == "haseeb" and post["author"]["name"] == "Haseeb"
    assert post["author"]["avatar_url"] == person["avatar_url"] and post["is_mine"] is False and post["poll"] is True
    assert [p["id"] for p in post["products"]] == [product.id]

    # the team panel shows where the look was posted, and the person's post count
    panel = (await client.get("/api/v1/team/looks")).json()
    assert [x["community"] for x in panel if x["id"] == look["id"]] == [[{"post_id": post_id, "handle": "haseeb"}]]
    assert (await client.get("/api/v1/team/people")).json()[0]["posts"] == 1

    # a team person can't sign in, and gets no emails
    stored = await db.get(User, person["id"])
    assert stored.hashed_password is None and stored.notify_email is False and stored.team_person is True


async def test_a_team_member_posts_a_try_on_as_a_person_from_the_post_window(client, db, monkeypatch):  # noqa: ANN001
    job_id, _product = await _finished_look(client, db, monkeypatch)
    me = (await client.get("/api/v1/auth/me")).json()
    body = {"tryon_job_id": job_id, "caption": "New look", "accept_rules": True}

    # a member who isn't on the team can't post as someone else
    assert (await client.post("/api/v1/community/posts", json={**body, "person_id": me["id"]})).status_code == 403

    await _team(db, me["id"])
    photo = {"photo": ("ayesha.jpg", small_jpeg_bytes(), "image/jpeg")}
    person = (await client.post("/api/v1/team/people", data={"name": "Ayesha", "handle": "ayesha"}, files=photo)).json()
    # only a team person, not any member's account
    assert (await client.post("/api/v1/community/posts", json={**body, "person_id": me["id"]})).status_code == 404

    made = await client.post("/api/v1/community/posts", json={**body, "person_id": person["id"]})
    assert made.status_code == 201, made.text
    assert made.json()["author"]["handle"] == "ayesha" and made.json()["author"]["name"] == "Ayesha"
    assert (await client.post("/api/v1/community/posts", json={**body, "person_id": person["id"]})).status_code == 409
    # the team member can still post the same look as themselves
    assert (await client.post("/api/v1/community/posts", json=body)).status_code == 201


async def test_the_team_panel_history_lists_finished_and_failed_try_ons(client, db, monkeypatch):  # noqa: ANN001
    from app.models.enums import JobStatus
    from app.models.tryon import TryOnJob

    job_id, product = await _finished_look(client, db, monkeypatch)
    me = (await client.get("/api/v1/auth/me")).json()
    assert (await client.get("/api/v1/team/tryons")).status_code == 403
    await _team(db, me["id"])

    done = await db.get(TryOnJob, job_id)
    failed = TryOnJob(
        user_id=me["id"], user_photo_id=done.user_photo_id, product_id=product.id, provider="openai",
        provider_model="test", status=JobStatus.FAILED, credit_cost=10, error_message="The picture couldn't be made.",
    )
    db.add(failed)
    await db.commit()

    history = (await client.get("/api/v1/team/tryons")).json()
    assert history["total"] >= 2 and history["failed"] >= 1 and history["done"] >= 1
    rows = {r["id"]: r for r in history["items"]}
    assert rows[job_id]["status"] == "done" and rows[job_id]["image_url"] and rows[job_id]["what"] == product.name
    assert rows[failed.id]["status"] == "failed" and rows[failed.id]["error"] == "The picture couldn't be made."
    assert rows[failed.id]["image_url"]  # the photo it started from
    assert rows[job_id]["community"] == []

    # posted to the community straight from the history (no Ready look needed)
    photo = {"photo": ("danish.jpg", small_jpeg_bytes(), "image/jpeg")}
    person = (await client.post("/api/v1/team/people", data={"name": "Danish", "handle": "danish"}, files=photo)).json()
    post = await client.post(
        "/api/v1/community/posts", json={"tryon_job_id": job_id, "accept_rules": True, "person_id": person["id"], "poll": True}
    )
    assert post.status_code == 201, post.text
    again = {r["id"]: r for r in (await client.get("/api/v1/team/tryons")).json()["items"]}
    assert again[job_id]["community"] == [{"post_id": post.json()["id"], "handle": "danish"}]

    only_failed = (await client.get("/api/v1/team/tryons", params={"show": "failed"})).json()
    assert {r["status"] for r in only_failed["items"]} == {"failed"}
