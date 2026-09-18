"""Put the person's own face back on a try-on result.

Every try-on model (FASHN, OpenAI image editing) generates a new image, so
the face drifts even when told to keep it. After the outfit is rendered we
find the face in the original photo and in the result, lift the original
head (hair, face, beard), scale and align it onto the result's face, and
Poisson-blend it in so there's no visible seam. The clothes come from the
model; the face stays the person's.

Deliberately conservative: if either face isn't found, or the two don't
plausibly match in size and position (a false detection, a very different
framing), the result is returned untouched rather than risk pasting a face
in the wrong place.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# how far the lifted head reaches beyond the detected face box, as a share of
# the box: up for hair, sideways for ears/hair, down for the beard/chin
_UP, _SIDE, _DOWN = 0.55, 0.28, 0.32
_MAX_SCALE_CHANGE = 1.6  # result face vs original face size
_MAX_CENTER_SHIFT = 0.12  # share of the image size the face may move between the two


@dataclass(frozen=True, slots=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def detect_face(img: np.ndarray) -> Box | None:
    """The largest frontal face, or None."""
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    min_side = max(24, min(img.shape[:2]) // 25)
    faces = _CASCADE.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(min_side, min_side))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return Box(int(x), int(y), int(w), int(h))


def _decode(data: bytes) -> np.ndarray | None:
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def restore_face_arrays(
    original: np.ndarray, result: np.ndarray, face_o: Box, face_r: Box
) -> np.ndarray | None:
    oh, ow = original.shape[:2]
    rh, rw = result.shape[:2]

    scale = face_r.w / face_o.w
    if not 1 / _MAX_SCALE_CHANGE < scale < _MAX_SCALE_CHANGE:
        return None
    if (
        abs(face_o.cx / ow - face_r.cx / rw) > _MAX_CENTER_SHIFT
        or abs(face_o.cy / oh - face_r.cy / rh) > _MAX_CENTER_SHIFT
    ):
        return None

    # the original head, cut generously around the face box
    left = max(0, int(face_o.x - _SIDE * face_o.w))
    right = min(ow, int(face_o.x + face_o.w * (1 + _SIDE)))
    top = max(0, int(face_o.y - _UP * face_o.h))
    bottom = min(oh, int(face_o.y + face_o.h * (1 + _DOWN)))
    head = original[top:bottom, left:right]

    # The detector's boxes are only roughly placed, so refine: try sizes
    # around the box ratio and slide the head over the result's head area,
    # keeping the placement that lines up best.
    gray_r = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    best: tuple[float, float, int, int] | None = None  # (score, scale, dx, dy)
    for s in (scale * f for f in (0.9, 0.95, 1.0, 1.05, 1.1)):
        patch = cv2.resize(head, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        ph, pw = patch.shape[:2]
        guess_x = int(round(face_r.cx - (face_o.cx - left) * s))
        guess_y = int(round(face_r.cy - (face_o.cy - top) * s))
        slack = int(0.25 * face_r.w)
        sx0, sy0 = max(0, guess_x - slack), max(0, guess_y - slack)
        sx1, sy1 = min(rw, guess_x + pw + slack), min(rh, guess_y + ph + slack)
        if sx1 - sx0 <= pw or sy1 - sy0 <= ph:
            continue
        scores = cv2.matchTemplate(
            gray_r[sy0:sy1, sx0:sx1], cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY), cv2.TM_CCOEFF_NORMED
        )
        _, score, _, (mx, my) = cv2.minMaxLoc(scores)
        if best is None or score > best[0]:
            best = (score, s, sx0 + mx, sy0 + my)
    if best is None:
        s = scale
        dx = int(round(face_r.cx - (face_o.cx - left) * s))
        dy = int(round(face_r.cy - (face_o.cy - top) * s))
    else:
        _, s, dx, dy = best

    patch = cv2.resize(head, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    ph, pw = patch.shape[:2]
    x0, y0 = max(dx, 0), max(dy, 0)
    x1, y1 = min(dx + pw, rw), min(dy + ph, rh)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None

    # a soft-edged ellipse over the head: the face itself is the original
    # pixels exactly, fading into the result at the hairline/beard edge so
    # no seam shows and the original collar/background corners stay out
    mask = np.zeros((ph, pw), np.float32)
    cv2.ellipse(mask, (pw // 2, ph // 2), (max(1, int(pw * 0.44)), max(1, int(ph * 0.46))), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), max(1.0, 0.06 * pw))[..., None]

    out = result.copy()
    region = out[y0:y1, x0:x1].astype(np.float32)
    src = patch[y0 - dy : y1 - dy, x0 - dx : x1 - dx].astype(np.float32)
    m = mask[y0 - dy : y1 - dy, x0 - dx : x1 - dx]
    out[y0:y1, x0:x1] = (src * m + region * (1 - m)).astype(np.uint8)
    return out


def restore_face(original_bytes: bytes, result_bytes: bytes) -> bytes | None:
    """JPEG bytes of the result with the original face put back, or None
    when it can't be done safely (the caller keeps the result as-is)."""
    original = _decode(original_bytes)
    result = _decode(result_bytes)
    if original is None or result is None:
        return None
    face_o = detect_face(original)
    face_r = detect_face(result)
    if face_o is None or face_r is None:
        return None
    restored = restore_face_arrays(original, result, face_o, face_r)
    if restored is None:
        return None
    ok, buf = cv2.imencode(".jpg", restored, [cv2.IMWRITE_JPEG_QUALITY, 93])
    return buf.tobytes() if ok else None
