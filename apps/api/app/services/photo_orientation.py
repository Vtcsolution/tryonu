"""Recovering the orientation of a photo stored before the EXIF fix.

Every photo uploaded before validate_and_optimize() applied EXIF rotation
had that tag stripped without ever being read — for any photo actually
sideways, that information is gone for good; there is no raw original
to reprocess (confirmed: only the processed JPEG is ever stored). The one
thing left to go on is the photo's own content: try every quarter-turn and
see which one a face detector agrees is upright. Deliberately conservative
— more than one rotation finding a face, or none at all, is reported as
unresolvable rather than guessed at, the same caution detect_face() itself
already uses for its own single-image case.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.services.face_restore import Box, detect_face

ROTATIONS = (0, 90, 180, 270)


@dataclass(frozen=True, slots=True)
class OrientationGuess:
    rotation: int | None  # degrees to rotate clockwise to make it upright; None = unresolved
    confident: bool
    candidates: tuple[int, ...]  # every rotation a face was found at, for the report


def _rotate(img: np.ndarray, degrees: int) -> np.ndarray:
    if degrees == 0:
        return img
    code = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[degrees]
    return cv2.rotate(img, code)


def guess_orientation(img: np.ndarray) -> OrientationGuess:
    """Which quarter-turn (if any) a face detector agrees makes this photo
    upright. `img` is the photo exactly as currently stored."""
    hits: list[tuple[int, Box]] = []
    for degrees in ROTATIONS:
        box = detect_face(_rotate(img, degrees))
        if box is not None:
            hits.append((degrees, box))

    if len(hits) != 1:
        # zero hits: no face this detector can find at any rotation — not
        # evidence of anything. More than one: at least one is a false
        # positive (a real photo has one real orientation), and which one
        # is right isn't decidable from this signal alone.
        return OrientationGuess(rotation=None, confident=False, candidates=tuple(d for d, _ in hits))

    degrees, _ = hits[0]
    return OrientationGuess(rotation=degrees, confident=True, candidates=(degrees,))
