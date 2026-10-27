"""Find the look: a photo in, the items in it out, each with real shop
products (exact matches first, then the nearest ones). The vision model and
the shops are stood in for here — no paid call, no network."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.config import get_settings
from app.retailers.base import RawProduct
from app.services import visual_search_service as lens
from app.services.live_search_service import LiveSearchResult
from tests.conftest import register_and_login, small_jpeg_bytes
from tests.test_shared_looks import _finished_look

SHOP = SimpleNamespace(slug="ebay", display_name="eBay")


def _result(pid: str, name: str, price: int = 2500) -> LiveSearchResult:
    return LiveSearchResult(
        provider=SHOP,  # type: ignore[arg-type]
        raw=RawProduct(retailer_product_id=pid, name=name, price_cents=price, product_url=f"https://shop.example/{pid}", images=[f"https://img.example/{pid}.jpg"]),
    )


CATALOG = {
    "women pink embroidered kurta": [
        _result("k1", "Pink Embroidered Chiffon Kurta Women"),
        _result("k2", "Blue Cotton Kurta Women"),
        _result("k3", "Women Pink Lawn Kurti"),
    ],
    "women gold khussa": [],  # nothing for the precise words...
    "women khussa": [_result("s1", "Golden Embroidered Khussa Flats"), _result("s2", "Black Leather Khussa")],  # ...the broader ones do
}


def _stand_ins(monkeypatch, calls: list) -> None:  # noqa: ANN001
    async def fake_vision(instructions: str, content: list[dict]) -> dict:
        calls.append(instructions[:20])
        if "Google Lens" in instructions:  # what's in the photo
            return {
                "gender": "women",
                "summary": "A pink embroidered kurta with gold khussa.",
                "items": [
                    {"label": "embroidered kurta", "category": "top", "query": "women pink embroidered kurta!", "broad_query": "women kurta",
                     "color": "pink", "details": "chiffon, floral embroidery", "box": [0.2, 0.1, 0.8, 0.6]},
                    {"label": "Khussa", "category": "shoes", "query": "women gold khussa", "broad_query": "women khussa", "color": "gold",
                     "box": [0.3, 0.85, 0.7, 1.4]},
                    {"label": "", "query": "nothing"},  # unusable: skipped
                ],
            }
        # comparing: product 1 of the kurta search is the same product, product 2 far off
        texts = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
        if "Kurta" in texts:
            return {"scores": [{"n": 1, "score": 93, "same": True}, {"n": 2, "score": 12, "same": False}, {"n": 3, "score": 74, "same": False}]}
        return {"scores": [{"n": 1, "score": 81, "same": False}, {"n": 2, "score": 30, "same": False}]}

    async def fake_search(query: str, *, limit: int = 24):  # noqa: ANN202
        return list(CATALOG.get(query, []))

    monkeypatch.setattr(lens, "_vision", fake_vision)
    monkeypatch.setattr(lens, "live_search", fake_search)
    monkeypatch.setattr(lens, "_thumbnail", lambda url: small_jpeg_bytes((120, 160)))
    monkeypatch.setattr(get_settings(), "OPENAI_API_KEY", "test-key-not-real")


async def test_a_photo_finds_its_products(client, monkeypatch):  # noqa: ANN001
    calls: list = []
    _stand_ins(monkeypatch, calls)
    await register_and_login(client)
    assert (await client.post("/api/v1/lens", files={"file": ("x.txt", b"not a photo", "text/plain")})).status_code == 400

    res = await client.post("/api/v1/lens", files={"file": ("look.jpg", small_jpeg_bytes((900, 1200)), "image/jpeg")})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["summary"].startswith("A pink") and body["image_url"] and (body["width"], body["height"]) == (900, 1200)
    kurta, khussa = body["items"]
    assert kurta["label"] == "Embroidered kurta" and kurta["query"] == "women pink embroidered kurta"  # tidied
    assert [m["product"]["retailer_product_id"] for m in kurta["matches"]] == ["k1", "k3", "k2"]  # closest first
    assert kurta["matches"][0]["match"] == "exact" and kurta["matches"][1]["match"] == "similar"
    assert kurta["matches"][0]["product"]["search_term"] == "women pink embroidered kurta"  # what select-live needs
    assert khussa["box"] == [0.0, 0.0, 1.0, 1.0] or khussa["box"][3] <= 1.0  # a box off the photo is kept inside it
    assert [m["product"]["retailer_product_id"] for m in khussa["matches"]] == ["s1", "s2"]  # found with the broader words
    assert khussa["matches"][0]["match"] == "close"  # very close (81), but not said to be the same
    assert khussa["matches"][1]["match"] == "similar"

    # kept: listed, opened again, deleted
    mine = (await client.get("/api/v1/lens")).json()
    assert mine[0]["id"] == body["id"] and mine[0]["items"] == 2
    assert (await client.get(f"/api/v1/lens/{body['id']}")).json()["items"][0]["matches"][0]["score"] == 93
    assert (await client.get(f"/api/v1/lens/{body['id']}")).json()["mine"] is True
    # its link works for anyone (sent to a friend), but only the owner can delete it
    await register_and_login(client)
    seen = await client.get(f"/api/v1/lens/{body['id']}")
    assert seen.status_code == 200 and seen.json()["mine"] is False and seen.json()["items"]
    assert (await client.delete(f"/api/v1/lens/{body['id']}")).status_code == 404
    await client.post("/api/v1/auth/logout")
    assert (await client.get(f"/api/v1/lens/{body['id']}")).status_code == 200  # no account needed to look


async def test_my_own_look_and_the_daily_allowance(client, db, monkeypatch):  # noqa: ANN001
    calls: list = []
    job_id, _ = await _finished_look(client, db, monkeypatch)
    _stand_ins(monkeypatch, calls)
    found = await client.post("/api/v1/lens/from", json={"tryon_job_id": job_id})
    assert found.status_code == 200, found.text
    assert len(found.json()["items"]) == 2

    monkeypatch.setattr(get_settings(), "LENS_DAILY_LIMIT", 1)
    again = await client.post("/api/v1/lens/from", json={"tryon_job_id": job_id})
    assert again.status_code == 429

    # no key on the server: a clear message, not a crash
    monkeypatch.setattr(get_settings(), "LENS_DAILY_LIMIT", 30)
    monkeypatch.setattr(get_settings(), "OPENAI_API_KEY", None)
    off = await client.post("/api/v1/lens", files={"file": ("look.jpg", small_jpeg_bytes(), "image/jpeg")})
    assert off.status_code == 503
