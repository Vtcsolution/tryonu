"""My looks (the Gallery), "this came out wrong", and how garments go on the look board."""

from __future__ import annotations

from sqlalchemy import update

from app.email.registry import get_email_provider
from app.models.user import User
from tests.conftest import credit_balance, register_and_login
from tests.test_shared_looks import _finished_look


async def test_the_gallery_lists_my_finished_looks_a_page_at_a_time(client, db, monkeypatch):  # noqa: ANN001
    job_id, _product = await _finished_look(client, db, monkeypatch)
    page = (await client.get("/api/v1/tryon/gallery", params={"limit": 1})).json()
    assert page["total"] >= 1 and page["items"][0]["job_id"] == job_id and page["items"][0]["image_url"]
    await register_and_login(client)
    assert (await client.get("/api/v1/tryon/gallery")).json()["total"] == 0  # only their own


async def test_a_reported_try_on_can_be_refunded_once_by_an_admin(client, db, monkeypatch):  # noqa: ANN001
    job_id, _product = await _finished_look(client, db, monkeypatch)
    me = (await client.get("/api/v1/auth/me")).json()
    made = await client.post(f"/api/v1/tryon/{job_id}/report", json={"reason": "merged", "note": "Two jackets became one"})
    assert made.status_code == 201, made.text
    assert (await client.post(f"/api/v1/tryon/{job_id}/report", json={"reason": "other"})).status_code == 409

    assert (await client.get("/api/v1/admin/tryon-reports")).status_code == 403
    await db.execute(update(User).where(User.id == me["id"]).values(is_admin=True))
    await db.commit()
    listed = (await client.get("/api/v1/admin/tryon-reports")).json()
    report = next(r for r in listed if r["job_id"] == job_id)
    assert report["note"] == "Two jackets became one" and report["image_url"]

    before = await credit_balance(db, me["id"])
    sent_before = len(get_email_provider().sent)
    done = await client.post(f"/api/v1/admin/tryon-reports/{report['id']}/refund")
    assert done.status_code == 200, done.text
    db.expire_all()
    assert await credit_balance(db, me["id"]) == before + report["credit_cost"]
    assert any(m["to"] == me["email"] for m in get_email_provider().sent[sent_before:])
    assert (await client.post(f"/api/v1/admin/tryon-reports/{report['id']}/refund")).status_code == 409


def test_separate_garments_get_their_own_label_on_the_look_board():
    from app.services.tryon_direct.look_board import BoardItem, build_look_board
    from tests.conftest import small_jpeg_bytes

    items = [
        BoardItem(small_jpeg_bytes(), "https://x.test/a.jpg", "Men Black Leather Jacket", True, "Jacket or coat"),
        BoardItem(small_jpeg_bytes(), "https://x.test/b.jpg", "Men Black Trousers", True, "Bottom"),
    ]
    _, labels = build_look_board(items)
    assert labels == ["Jacket or coat", "Bottom"]


async def test_a_photo_gets_a_first_guess_of_the_clothing_section(client, monkeypatch):  # noqa: ANN001
    from tests.test_tryon import _upload_front_photo

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)

    async def fake_ask(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202 - never the real (paid) vision call
        return {"section": "men", "framing": "upper_body", "facing_camera": True}

    monkeypatch.setattr("app.services.tryon_quality.vision.ask_json", fake_ask)
    body = (await client.post(f"/api/v1/photos/{photo_id}/analysis")).json()
    assert body == {"audience": "men", "framing": "upper_body", "facing_camera": True}

    async def unsure(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return {"section": "unsure", "framing": "full_body"}

    monkeypatch.setattr("app.services.tryon_quality.vision.ask_json", unsure)
    assert (await client.post(f"/api/v1/photos/{photo_id}/analysis")).json()["audience"] is None
