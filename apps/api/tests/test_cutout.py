"""product_cutout_mask() against the real u2netp model — unlike the rest
of the try-on test suite, this one genuinely runs local CPU inference
(and downloads ~4.5MB of ONNX weights on a machine's first-ever run,
cached under ~/.rembg/models/ after that; never downloaded at import
time, only when a cutout is actually requested). Kept in its own file so
it's easy to see this is the one real exception to "zero network" in
this suite, and to skip deliberately if ever needed."""

from __future__ import annotations

import numpy as np

from app.services.tryon_quality.cutout import product_cutout_mask


def _studio_photo(product_bgr: tuple[int, int, int]) -> np.ndarray:
    img = np.full((300, 300, 3), (245, 245, 245), dtype=np.uint8)
    img[75:225, 75:225] = product_bgr
    return img


def test_real_cutout_finds_the_product_not_the_backdrop():
    img = _studio_photo((0, 0, 220))
    mask = product_cutout_mask(img, "https://img.example/real-cutout-test-red.jpg")
    assert mask.shape == img.shape[:2]
    assert mask[150, 150] > 127  # centre of the product: foreground
    assert mask[10, 10] < 127  # corner of the backdrop: background


def test_real_cutout_is_cached_on_the_second_call(monkeypatch):
    from app.services.tryon_quality import cutout as cutout_module

    calls = []
    orig_get_session = cutout_module._get_session
    monkeypatch.setattr(cutout_module, "_get_session", lambda: (calls.append(1), orig_get_session())[1])

    img = _studio_photo((40, 160, 40))
    url = "https://img.example/real-cutout-test-green-cache.jpg"
    first = product_cutout_mask(img, url)  # cold: real inference, writes the cache
    assert len(calls) == 1
    second = product_cutout_mask(img, url)  # warm: must hit the cache, never call the model again
    assert np.array_equal(first, second)
    assert len(calls) == 1
