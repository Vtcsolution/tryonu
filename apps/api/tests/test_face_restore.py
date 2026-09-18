"""Putting the person's own face back on a try-on result — the models redraw
faces and they drift (real complaint: "the face has totally changed")."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from sqlalchemy import select

from app.services.face_restore import Box, restore_face, restore_face_arrays
from tests.conftest import register_and_login, seed_product


def _textured(h: int = 600, w: int = 400, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    return cv2.GaussianBlur(noise, (0, 0), 3)


def test_restores_the_original_face_onto_a_rescaled_render():
    original = _textured()
    face_o = Box(150, 120, 100, 110)
    # a 2k-style render: bigger, and the model redrew the face
    result = cv2.resize(original, None, fx=1.2, fy=1.2)
    face_r = Box(180, 144, 120, 132)
    result[face_r.y : face_r.y + face_r.h, face_r.x : face_r.x + face_r.w] = (40, 60, 160)

    restored = restore_face_arrays(original, result, face_o, face_r)
    assert restored is not None

    expected = cv2.resize(original, None, fx=1.2, fy=1.2)
    inner = (slice(face_r.y + 20, face_r.y + face_r.h - 20), slice(face_r.x + 20, face_r.x + face_r.w - 20))
    drifted_err = np.abs(result[inner].astype(float) - expected[inner]).mean()
    restored_err = np.abs(restored[inner].astype(float) - expected[inner]).mean()
    assert restored_err < drifted_err / 5
    # outside the head nothing changes — the outfit is the model's
    assert np.array_equal(restored[500:, :], result[500:, :])


@pytest.mark.parametrize(
    "face_r",
    [
        Box(180, 144, 300, 330),  # far bigger: a false detection, not the same face
        Box(20, 500, 100, 110),  # somewhere else entirely in the frame
    ],
)
def test_leaves_the_result_alone_when_the_faces_dont_match(face_r):
    original = _textured()
    result = _textured(seed=2)
    assert restore_face_arrays(original, result, Box(150, 120, 100, 110), face_r) is None


def test_no_face_found_means_no_change():
    ok, a = cv2.imencode(".jpg", np.full((300, 200, 3), 128, np.uint8))
    assert restore_face(a.tobytes(), a.tobytes()) is None


async def _finished_single_item_tryon(client, db, monkeypatch):
    from app.ai.providers.base import TryOnOutput
    from app.ai.providers.mock import MockTryOnProvider
    from app.models.tryon import TryOnResult
    from app.services.storage_service import get_storage
    from tests.conftest import small_jpeg_bytes
    from tests.test_tryon import _poll_until_terminal, _upload_front_photo

    async def instant_render(self, payload):  # noqa: ARG001 — the mock otherwise simulates render latency
        return TryOnOutput(image_bytes=small_jpeg_bytes(color=(10, 200, 10)))

    monkeypatch.setattr(MockTryOnProvider, "generate", instant_render)

    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Cotton Shirt")
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    finished = await _poll_until_terminal(client, resp.json()["id"])
    assert finished["status"] == "completed", finished
    row = (await db.execute(select(TryOnResult).where(TryOnResult.job_id == finished["id"]))).scalar_one()
    return get_storage().read(row.storage_key)


async def test_every_finished_tryon_gets_the_original_face_back(client, db, monkeypatch):
    seen: list[tuple[int, int]] = []

    def fake_restore(original: bytes, result: bytes) -> bytes:
        seen.append((len(original), len(result)))
        return b"\xff\xd8restored"

    monkeypatch.setattr("app.workers.tasks.tryon_tasks.restore_face", fake_restore)
    stored = await _finished_single_item_tryon(client, db, monkeypatch)
    assert stored == b"\xff\xd8restored"
    assert seen and seen[0][0] > 0  # read the person's own uploaded photo


async def test_a_failed_face_restore_never_loses_the_render(client, db, monkeypatch):
    def broken_restore(original: bytes, result: bytes) -> bytes:
        raise RuntimeError("opencv exploded")

    monkeypatch.setattr("app.workers.tasks.tryon_tasks.restore_face", broken_restore)
    stored = await _finished_single_item_tryon(client, db, monkeypatch)
    assert stored[:2] == b"\xff\xd8"  # the model's own render, untouched


def test_head_worn_items_are_recognised():
    from app.services.outfit_slots import worn_on_head

    for name in ("Black Wool Fedora Hat", "Aviator Sunglasses UV400", "Gold Jhumka Earrings", "Rajasthani Pagri",
                 "Bridal Maang Tikka", "Chiffon Hijab Scarf"):
        assert worn_on_head(name), name
    for name in ("Cotton Shalwar Kameez", "Leather Oxford Shoes", "Bulova Blue Dial Watch", "Duffle Bag"):
        assert not worn_on_head(name), name


async def test_face_restore_skips_looks_with_something_on_the_head(client, db, monkeypatch):
    """Putting the original head back would erase a hat or sunglasses the
    model just drew."""

    def must_not_run(original: bytes, result: bytes) -> bytes:
        raise AssertionError("would paint over the hat")

    monkeypatch.setattr("app.workers.tasks.tryon_tasks.restore_face", must_not_run)
    from app.ai.providers.base import TryOnOutput
    from app.ai.providers.mock import MockTryOnProvider
    from tests.conftest import small_jpeg_bytes
    from tests.test_tryon import _poll_until_terminal, _upload_front_photo

    async def instant_render(self, payload):  # noqa: ARG001
        return TryOnOutput(image_bytes=small_jpeg_bytes())

    monkeypatch.setattr(MockTryOnProvider, "generate", instant_render)
    await register_and_login(client)
    photo_id = await _upload_front_photo(client)
    product = await seed_product(db, name="Black Wool Fedora Hat")
    resp = await client.post("/api/v1/tryon", json={"user_photo_id": photo_id, "product_id": product.id})
    finished = await _poll_until_terminal(client, resp.json()["id"])
    assert finished["status"] == "completed", finished


async def test_face_restore_can_be_switched_off(client, db, monkeypatch):
    def must_not_run(original: bytes, result: bytes) -> bytes:
        raise AssertionError("face restore is off")

    monkeypatch.setattr("app.workers.tasks.tryon_tasks.restore_face", must_not_run)
    monkeypatch.setattr("app.workers.tasks.tryon_tasks.settings.TRYON_KEEP_ORIGINAL_FACE", False)
    await _finished_single_item_tryon(client, db, monkeypatch)
