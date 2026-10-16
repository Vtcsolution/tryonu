"""Product photos through TryOnU's own server."""

from __future__ import annotations

import io

from PIL import Image

from app.api.v1.endpoints import image_proxy


def _png(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (width, height), (200, 30, 30, 255)).save(out, format="PNG")
    return out.getvalue()


async def test_a_photo_is_relayed_smaller_and_kept(client, monkeypatch, tmp_path):
    calls = []

    def fake_fetch(url, *, max_bytes, timeout):  # noqa: ANN001, ANN202, ARG001
        calls.append(url)
        return _png(1600, 2000)

    monkeypatch.setattr(image_proxy, "fetch_limited", fake_fetch)
    monkeypatch.setattr(image_proxy, "_cache_dir", lambda: tmp_path)
    url = "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"

    first = await client.get("/api/v1/img", params={"u": url, "w": 600})
    assert first.status_code == 200 and first.headers["content-type"] == "image/jpeg"
    assert "max-age" in first.headers["cache-control"]
    assert Image.open(io.BytesIO(first.content)).width == 600

    again = await client.get("/api/v1/img", params={"u": url, "w": 600})
    assert again.status_code == 200 and calls == [url]  # fetched once, then kept


async def test_private_addresses_are_never_fetched(client, monkeypatch, tmp_path):
    monkeypatch.setattr(image_proxy, "_cache_dir", lambda: tmp_path)
    for bad in ("http://127.0.0.1/admin.png", "http://localhost/x.jpg", "file:///etc/passwd"):
        resp = await client.get("/api/v1/img", params={"u": bad})
        assert resp.status_code in (400, 422), bad


async def test_a_broken_image_is_a_404_not_a_crash(client, monkeypatch, tmp_path):
    monkeypatch.setattr(image_proxy, "fetch_limited", lambda url, **kw: b"not an image")
    monkeypatch.setattr(image_proxy, "_cache_dir", lambda: tmp_path)
    resp = await client.get("/api/v1/img", params={"u": "https://i.ebayimg.com/x.jpg"})
    assert resp.status_code == 404
