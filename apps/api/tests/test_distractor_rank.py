"""rank_against_distractors()'s own ranking logic, with embed_image()
mocked to fixed vectors — zero network, zero model load. The real CLIP
model is exercised for real in test_clip_embed.py instead; what's under
test here is the rank/margin arithmetic given known similarities."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.tryon_quality import distractor_rank as rank_module
from app.services.tryon_quality.distractor_rank import DistractorRank, rank_against_distractors

# Dummy "images" — embed_image is mocked below, so their actual pixel
# content never matters, only which object identity maps to which vector.
_RENDERED = np.zeros((4, 4, 3), np.uint8)
_PRODUCT = np.ones((4, 4, 3), np.uint8)


def _mock_embed(vectors: dict[int, np.ndarray]):
    def fake_embed_image(image: np.ndarray) -> np.ndarray:
        return vectors[id(image)]

    return fake_embed_image


def _unit(vec: list[float]) -> np.ndarray:
    arr = np.array(vec, dtype=np.float32)
    return arr / np.linalg.norm(arr)


async def test_the_chosen_product_ranks_first_when_it_is_the_best_match(monkeypatch):
    distractor_a, distractor_b = np.full((4, 4, 3), 2, np.uint8), np.full((4, 4, 3), 3, np.uint8)
    vectors = {
        id(_RENDERED): _unit([1.0, 0.0]),
        id(_PRODUCT): _unit([1.0, 0.0]),  # identical to the render: similarity 1.0
        id(distractor_a): _unit([0.0, 1.0]),  # orthogonal: similarity 0.0
        id(distractor_b): _unit([0.5, 0.5]),
    }
    monkeypatch.setattr(rank_module, "embed_image", _mock_embed(vectors))

    result = rank_against_distractors(_RENDERED, _PRODUCT, [distractor_a, distractor_b])

    assert result.rank == 1
    assert result.total == 3
    assert result.chosen_similarity == pytest.approx(1.0, abs=1e-5)
    assert result.margin > 0


async def test_a_distractor_that_matches_better_outranks_the_chosen_product(monkeypatch):
    """The live-bug class this exists to catch: the render actually
    resembles a different product more than the one the customer picked."""
    look_alike = np.full((4, 4, 3), 9, np.uint8)
    vectors = {
        id(_RENDERED): _unit([1.0, 0.0]),
        id(_PRODUCT): _unit([0.0, 1.0]),  # orthogonal to the render: similarity 0.0
        id(look_alike): _unit([1.0, 0.01]),  # nearly identical to the render
    }
    monkeypatch.setattr(rank_module, "embed_image", _mock_embed(vectors))

    result = rank_against_distractors(_RENDERED, _PRODUCT, [look_alike])

    assert result.rank == 2  # the chosen product is NOT the closest match
    assert result.margin < 0  # a distractor won


async def test_no_distractors_still_ranks_first_with_no_margin_penalty(monkeypatch):
    vectors = {id(_RENDERED): _unit([1.0, 0.0]), id(_PRODUCT): _unit([1.0, 0.0])}
    monkeypatch.setattr(rank_module, "embed_image", _mock_embed(vectors))

    result = rank_against_distractors(_RENDERED, _PRODUCT, [])

    assert result == DistractorRank(
        rank=1, total=1, chosen_similarity=pytest.approx(1.0, abs=1e-5),
        best_distractor_similarity=None, margin=pytest.approx(1.0, abs=1e-5),
    )


def test_log_distractor_rank_never_raises_on_a_missing_best_distractor(caplog):
    from app.services.tryon_quality.distractor_rank import log_distractor_rank

    result = DistractorRank(rank=1, total=1, chosen_similarity=0.9, best_distractor_similarity=None, margin=0.9)
    log_distractor_rank("job-123", "a red kurta", result)  # must not raise
