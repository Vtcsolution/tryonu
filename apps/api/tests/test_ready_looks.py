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
    assert "/affiliate/go/" in look["items"][0]["buy_url"]

    # anyone sees it on the page, with its pictures
    await client.post("/api/v1/auth/logout")
    listed = (await client.get("/api/v1/looks", params={"audience": "women"})).json()
    assert look["id"] in [x["id"] for x in listed]
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
    card = render_card(
        "Men's winter look",
        buf.getvalue(),
        [CardItem("Wool overcoat", "$120.00", small_jpeg_bytes()), CardItem("Ribbed wool scarf", "£225.00", None),
         CardItem("Chelsea boots", "$175.46", small_jpeg_bytes(), (0.4, 0.9, 0.6, 0.98))],
    )
    img = Image.open(io.BytesIO(card))
    assert img.size == (1080, 1350) and img.format == "JPEG"
