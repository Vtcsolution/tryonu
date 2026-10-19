"""Your size: measurements win over height and weight; loose fit goes a size up;
shoes convert between EU, UK and US."""

from __future__ import annotations

from app.services.size_service import suggest
from tests.conftest import register_and_login


def test_size_charts():
    assert suggest(gender="women", bust_cm=90, waist_cm=72, hips_cm=98).letter == "M"  # the largest measurement wins
    m = suggest(gender="women", height_cm=165, weight_kg=60)  # BMI 22
    assert (m.letter, m.uk, m.basis) == ("M", "12", "height_weight")
    assert suggest(gender="women", height_cm=165, weight_kg=60, fit="loose").letter == "L"
    man = suggest(gender="men", bust_cm=101, waist_cm=86)  # a 40-inch chest
    assert (man.letter, man.chest_in, man.trousers_waist_in) == ("M", "38–40", "34")
    assert suggest(gender="men", bust_cm=106).letter == "L"
    assert suggest(gender="men", height_cm=190, weight_kg=70).letter == "M"  # tall and slim: the length of an M
    assert suggest(gender="women", shoe_eu=39).shoe == {"eu": "39", "uk": "6", "us": "8"}
    assert suggest(gender="men", shoe_eu=42).shoe == {"eu": "42", "uk": "8", "us": "9"}
    assert suggest(gender="women") is None


async def test_a_member_saves_their_size(client):  # noqa: ANN001
    await register_and_login(client)
    assert (await client.get("/api/v1/users/me/size")).json()["suggestion"] is None
    saved = await client.put("/api/v1/users/me/size", json={"gender": "women", "height_cm": 160, "weight_kg": 70, "shoe_eu": 38})
    assert saved.status_code == 200, saved.text
    s = saved.json()["suggestion"]
    assert s["letter"] == "XL" and s["shoe"]["uk"] == "5"  # BMI 27.3
    assert (await client.put("/api/v1/users/me/size", json={"height_cm": 20})).status_code == 422
    again = (await client.get("/api/v1/users/me/size")).json()
    assert again["height_cm"] == 160 and again["gender"] == "women"
