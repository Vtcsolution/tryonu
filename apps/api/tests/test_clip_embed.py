"""embed_image() against the real CLIP ONNX vision encoder — unlike the
rest of the try-on test suite, this one genuinely runs local CPU
inference (and downloads the ~89MB quantized ONNX weights on a machine's
first-ever run, cached under data/clip/ after that; never downloaded at
import time, only when an embedding is actually requested). Kept in its
own file for the same reason test_cutout.py is: it's the one deliberate
exception to "zero network" in this suite."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.tryon_quality.clip_embed import cosine_similarity, embed_image


def _solid(color_bgr: tuple[int, int, int], size: int = 224) -> np.ndarray:
    return np.full((size, size, 3), color_bgr, dtype=np.uint8)


def test_real_embedding_is_unit_length():
    vec = embed_image(_solid((0, 0, 220)))
    assert vec.shape == (512,)
    assert np.linalg.norm(vec) == pytest.approx(1.0, abs=1e-4)


def test_near_identical_colours_embed_closer_than_unrelated_ones():
    red = embed_image(_solid((0, 0, 220)))
    near_red = embed_image(_solid((10, 10, 200)))
    blue = embed_image(_solid((220, 0, 0)))
    assert cosine_similarity(red, near_red) > cosine_similarity(red, blue)
