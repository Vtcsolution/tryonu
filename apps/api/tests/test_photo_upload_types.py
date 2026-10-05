"""Uploads are judged by their contents, not the type the browser claims."""

from __future__ import annotations

import pytest

from tests.conftest import register_and_login, small_jpeg_bytes


@pytest.mark.parametrize("declared", ["image/jpg", "application/octet-stream", "image/pjpeg", ""])
async def test_a_real_photo_is_accepted_whatever_type_the_browser_declares(client, declared):
    """Live: a normal JPEG was refused with 415 because of its declared type."""
    await register_and_login(client)
    resp = await client.post(
        "/api/v1/photos", files={"file": ("front.jpg", small_jpeg_bytes(), declared)}, data={"kind": "front"}
    )
    assert resp.status_code == 201, resp.text


async def test_a_file_that_is_not_an_image_is_still_refused(client):
    await register_and_login(client)
    resp = await client.post(
        "/api/v1/photos", files={"file": ("front.jpg", b"not an image at all", "image/jpeg")}, data={"kind": "front"}
    )
    assert resp.status_code == 400 and "not a valid image" in resp.text
