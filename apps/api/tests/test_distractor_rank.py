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


# --------------------------------------------- _distractor_images_for priority
#
# The "other options" saved on the job at creation time (the real set the
# shopper actually saw) must be used in preference to the same-category DB
# guess, whenever the client sent any.


class _FakeJob:
    def __init__(self, distractor_options):
        self.distractor_options = distractor_options


async def test_saved_distractor_options_are_used_instead_of_the_category_fallback(monkeypatch):
    from app.workers.tasks import tryon_tasks

    calls: list[str] = []

    async def fake_download(url: str):
        calls.append(url)
        return np.zeros((4, 4, 3), np.uint8)

    async def fail_if_called(*a, **kw):  # noqa: ARG001
        raise AssertionError("the same-category fallback must not run when options were saved")

    monkeypatch.setattr(tryon_tasks, "_download", fake_download)
    monkeypatch.setattr(tryon_tasks, "_distractors_for", fail_if_called)

    job = _FakeJob({"prod-1": [{"image_url": "https://img.example/a.jpg"}, {"image_url": "https://img.example/b.jpg"}]})
    layer = tryon_tasks._Layer(image_url="https://img.example/chosen.jpg", slot=None, name="a kurta", product_id="prod-1")

    images = await tryon_tasks._distractor_images_for(session=None, job=job, layer=layer)

    assert len(images) == 2
    assert calls == ["https://img.example/a.jpg", "https://img.example/b.jpg"]


# ------------------------------------- _distractors_for eager-loads images
#
# Live bug (2026-10-01): session.get(Product, ...) and the category query
# both fetched a Product without its `images` relationship loaded;
# .primary_image_url then lazy-loads it, which an AsyncSession refuses to
# do implicitly ("greenlet_spawn has not been called") -- caught live,
# after deploy, as tryon_distractor_rank_failed on every real job that hit
# the same-category fallback.


async def test_distractors_for_can_read_primary_image_url_without_a_lazy_load_error(db):
    from tests.conftest import seed_product
    from app.models.retailer import ProductCategory
    from app.workers.tasks.tryon_tasks import _distractors_for

    category = ProductCategory(slug="kurtis", name="Kurtis")
    db.add(category)
    await db.commit()

    chosen = await seed_product(db, name="Chosen Kurti", image_url="https://img.example/chosen.jpg")
    other = await seed_product(db, name="Other Kurti", image_url="https://img.example/other.jpg")
    chosen.category_id = other.category_id = category.id
    await db.commit()
    await db.refresh(chosen)

    distractors = await _distractors_for(db, chosen)

    assert len(distractors) == 1
    assert distractors[0].primary_image_url == "https://img.example/other.jpg"  # must not raise a lazy-load error
