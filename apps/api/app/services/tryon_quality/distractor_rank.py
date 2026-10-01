"""Shadow-mode identity check: does the rendered result actually look more
like the product the customer chose than like the OTHER products it could
be confused with — the other results from the same catalog search?

This never fails a render. It only logs (tryon_distractor_rank) the rank
of the chosen product's own image among the distractors', by CLIP
embedding similarity to the rendered crop, so a real pass/fail threshold
can be set later from actual logged scores rather than guessed at — the
same reasoning that kept the colour and presence gates (judge.py) from
shipping before they were tested against the live job's own case. See
app/scripts/calibrate_distractor_rank.py for calibrating this offline
against past completed jobs, with no new render and no paid call.

Distractors are the other active products in the chosen product's own
category — the catalog doesn't persist "this is the exact result set a
search returned," so the closest available, always-on proxy for "the
other results for the same query" is the same category filter
search_service.search_products itself would have applied.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.logging import logger
from app.services.tryon_quality.clip_embed import cosine_similarity, embed_image


@dataclass(frozen=True, slots=True)
class DistractorRank:
    rank: int  # 1 = the chosen product's own image is the closest match; higher is worse
    total: int  # how many candidates (the chosen product + its distractors) were compared
    chosen_similarity: float
    best_distractor_similarity: float | None
    margin: float  # chosen_similarity - best_distractor_similarity (negative: a distractor won)


def rank_against_distractors(
    rendered_crop: np.ndarray, product_image: np.ndarray, distractor_images: list[np.ndarray]
) -> DistractorRank:
    """Where the chosen product's own photo ranks, by how closely the
    RENDERED result resembles it, among the distractors' photos. Never
    asks what kind of product this is — only compares embeddings."""
    rendered_vec = embed_image(rendered_crop)
    chosen_sim = cosine_similarity(rendered_vec, embed_image(product_image))
    distractor_sims = [cosine_similarity(rendered_vec, embed_image(img)) for img in distractor_images]
    rank = 1 + sum(1 for sim in distractor_sims if sim > chosen_sim)
    best_distractor = max(distractor_sims) if distractor_sims else None
    margin = chosen_sim - best_distractor if best_distractor is not None else chosen_sim
    return DistractorRank(
        rank=rank,
        total=1 + len(distractor_sims),
        chosen_similarity=chosen_sim,
        best_distractor_similarity=best_distractor,
        margin=margin,
    )


def log_distractor_rank(job_id: str, item_name: str, result: DistractorRank) -> None:
    logger.info(
        "tryon_distractor_rank",
        job_id=job_id,
        item=item_name[:80],
        rank=result.rank,
        total=result.total,
        chosen_similarity=round(result.chosen_similarity, 4),
        best_distractor_similarity=(
            round(result.best_distractor_similarity, 4) if result.best_distractor_similarity is not None else None
        ),
        margin=round(result.margin, 4),
    )
