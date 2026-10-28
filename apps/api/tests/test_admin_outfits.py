"""Admin → All outfits: every finished try-on picture, shoppers' and the team's."""

from __future__ import annotations

from sqlalchemy import update

from app.models.user import User
from tests.conftest import register_and_login
from tests.test_shared_looks import _finished_look


async def test_admins_see_every_finished_outfit_with_who_made_it(client, db, monkeypatch):  # noqa: ANN001
    job_id, _product = await _finished_look(client, db, monkeypatch)
    maker = (await client.get("/api/v1/auth/me")).json()

    await register_and_login(client)
    me = (await client.get("/api/v1/auth/me")).json()
    assert (await client.get("/api/v1/admin/outfits")).status_code == 403  # not for members
    await db.execute(update(User).where(User.id == me["id"]).values(is_admin=True))
    await db.commit()

    found = (await client.get("/api/v1/admin/outfits", params={"q": maker["email"]})).json()
    row = next(i for i in found["items"] if i["id"] == job_id)
    assert row["user_email"] == maker["email"] and row["image_url"] and row["is_team"] is False
    assert row["ready_look_id"] is None and found["total"] >= 1

    team_only = (await client.get("/api/v1/admin/outfits", params={"who": "team", "q": maker["email"]})).json()
    assert job_id not in [i["id"] for i in team_only["items"]]
    members_only = (await client.get("/api/v1/admin/outfits", params={"who": "members", "q": maker["email"]})).json()
    assert job_id in [i["id"] for i in members_only["items"]]
