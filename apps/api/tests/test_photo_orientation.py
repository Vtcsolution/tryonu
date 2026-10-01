"""guess_orientation()'s own decision logic — detect_face() itself (a real
Haar cascade) is mocked here the same way the rest of the test suite never
exercises it against a real photographed face; what's under test is only
the rotate-four-ways-and-decide logic built on top of it."""

from __future__ import annotations

import numpy as np

from app.services import photo_orientation
from app.services.face_restore import Box
from app.services.photo_orientation import guess_orientation

_IMG = np.zeros((100, 100, 3), dtype=np.uint8)
_A_BOX = Box(x=10, y=10, w=20, h=20)


def test_a_face_found_only_upright_is_confident_and_zero(monkeypatch):
    def fake_detect(img):  # noqa: ANN001
        # the function always rotates `img` before calling detect_face —
        # tell rotation 0 apart from the rest by array identity
        return _A_BOX if img is _IMG else None

    monkeypatch.setattr(photo_orientation, "detect_face", fake_detect)
    monkeypatch.setattr(photo_orientation, "_rotate", lambda img, degrees: img if degrees == 0 else np.ones((1,)))
    result = guess_orientation(_IMG)
    assert result == photo_orientation.OrientationGuess(rotation=0, confident=True, candidates=(0,))


def test_a_face_found_only_at_90_reports_that_rotation(monkeypatch):
    rotated_marker = np.ones((1,))

    def fake_rotate(img, degrees):  # noqa: ANN001
        return rotated_marker if degrees == 90 else np.zeros((2,))

    def fake_detect(img):  # noqa: ANN001
        return _A_BOX if img is rotated_marker else None

    monkeypatch.setattr(photo_orientation, "_rotate", fake_rotate)
    monkeypatch.setattr(photo_orientation, "detect_face", fake_detect)
    result = guess_orientation(_IMG)
    assert result.rotation == 90 and result.confident


def test_no_face_at_any_rotation_is_unresolved_not_guessed(monkeypatch):
    monkeypatch.setattr(photo_orientation, "detect_face", lambda img: None)  # noqa: ARG005
    result = guess_orientation(_IMG)
    assert result.rotation is None
    assert not result.confident
    assert result.candidates == ()


def test_a_face_found_at_more_than_one_rotation_is_unresolved_not_guessed(monkeypatch):
    """A real photo has exactly one true orientation — two or more hits
    means at least one is a false positive, and this signal alone can't
    say which. Reported as unresolved rather than picking the larger box,
    the same conservatism detect_face() itself already applies."""
    monkeypatch.setattr(photo_orientation, "detect_face", lambda img: _A_BOX)  # noqa: ARG005
    result = guess_orientation(_IMG)
    assert result.rotation is None
    assert not result.confident
    assert set(result.candidates) == set(photo_orientation.ROTATIONS)


def test_rotate_zero_degrees_is_a_no_op():
    out = photo_orientation._rotate(_IMG, 0)
    assert out is _IMG


def test_rotate_180_reverses_a_simple_pattern():
    img = np.zeros((4, 4, 3), dtype=np.uint8)
    img[0, 0] = (255, 0, 0)  # top-left marker
    out = photo_orientation._rotate(img, 180)
    assert tuple(out[3, 3]) == (255, 0, 0)  # now bottom-right
