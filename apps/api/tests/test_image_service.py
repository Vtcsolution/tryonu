"""Upload processing: EXIF orientation must be applied before the
metadata strip that follows it, or it's gone for good — nothing
downstream (cv2.imdecode included) ever reads EXIF either."""

from __future__ import annotations

import io

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers
from PIL import Image, ImageDraw

from app.services.image_service import validate_and_optimize


def _upright_with_marker() -> Image.Image:
    """A portrait photo with a marker only in the top-left corner, so a
    wrong orientation is visually (and pixel-)detectable."""
    img = Image.new("RGB", (400, 600), color=(200, 200, 200))
    ImageDraw.Draw(img).rectangle([0, 0, 60, 60], fill=(255, 0, 0))
    return img


def _rotated_with_exif_orientation(img: Image.Image, orientation: int, angle: int) -> bytes:
    """`img` rotated by `angle` degrees (PIL's rotate: positive = CCW) —
    simulating a camera sensor's raw pixels — tagged with the EXIF
    orientation value that correctly describes how to undo that rotation,
    the same way a real phone photo is stored."""
    rotated = img.rotate(angle, expand=True)
    exif = Image.Exif()
    exif[0x0112] = orientation  # Orientation tag
    buf = io.BytesIO()
    rotated.save(buf, format="JPEG", quality=95, exif=exif.tobytes())
    return buf.getvalue()


def _as_upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="photo.jpg", headers=Headers({"content-type": "image/jpeg"}))


def _marker_corner(img: Image.Image) -> tuple[int, int, int]:
    """Average colour of the top-left 60x60 — where the marker is only
    when the image is genuinely upright."""
    corner = img.crop((0, 0, 60, 60))
    pixels = list(corner.getdata())
    r = sum(p[0] for p in pixels) / len(pixels)
    g = sum(p[1] for p in pixels) / len(pixels)
    b = sum(p[2] for p in pixels) / len(pixels)
    return (round(r), round(g), round(b))


@pytest.mark.asyncio
async def test_a_sideways_phone_photo_is_stored_upright():
    reference = _upright_with_marker()
    # EXIF 6: "rotate 90 CW to correct" — correctly describes pixels that
    # were rotated 90 CCW (PIL's rotate(90) is CCW), exactly how a phone
    # held sideways actually stores a photo.
    raw = _rotated_with_exif_orientation(reference, orientation=6, angle=90)

    processed = await validate_and_optimize(_as_upload(raw))

    result = Image.open(io.BytesIO(processed.content))
    assert _marker_corner(result)[0] > 150  # the red marker is back in the top-left, not rotated away
    assert _marker_corner(result)[1] < 100
    # upright means portrait again, not the landscape the raw sensor stored
    assert result.height > result.width


@pytest.mark.asyncio
async def test_a_180_rotated_photo_is_corrected_too():
    reference = _upright_with_marker()
    raw = _rotated_with_exif_orientation(reference, orientation=3, angle=180)

    processed = await validate_and_optimize(_as_upload(raw))

    result = Image.open(io.BytesIO(processed.content))
    assert _marker_corner(result)[0] > 150
    assert _marker_corner(result)[1] < 100


@pytest.mark.asyncio
async def test_an_already_upright_photo_is_unaffected():
    reference = _upright_with_marker()
    buf = io.BytesIO()
    reference.save(buf, format="JPEG", quality=95)

    processed = await validate_and_optimize(_as_upload(buf.getvalue()))

    result = Image.open(io.BytesIO(processed.content))
    assert _marker_corner(result)[0] > 150
    assert _marker_corner(result)[1] < 100
    assert result.height > result.width


@pytest.mark.asyncio
async def test_exif_metadata_is_still_stripped_after_being_applied():
    reference = _upright_with_marker()
    raw = _rotated_with_exif_orientation(reference, orientation=6, angle=90)

    processed = await validate_and_optimize(_as_upload(raw))

    result = Image.open(io.BytesIO(processed.content))
    assert result.getexif() == {} or not dict(result.getexif())  # nothing left to mis-rotate it again later
