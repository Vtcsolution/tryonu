from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.enums import JobStatus
from app.schemas.common import ORMModel
from app.schemas.outfit import OutfitOut
from app.schemas.photo import UserPhotoOut
from app.schemas.product import ProductOut
from app.schemas.wardrobe import WardrobeItemOut


class DistractorOption(BaseModel):
    """One of the "other options" the client showed alongside a selected
    item, at the moment of selection — used as the real distractor set
    for the shadow-mode identity check instead of a same-category guess."""

    product_id: str | None = None
    image_url: str


class CreateTryOnRequest(BaseModel):
    user_photo_id: str
    product_id: str | None = None
    outfit_id: str | None = None
    wardrobe_item_id: str | None = None
    # Keyed by the product_id of the selected item ("other options" the
    # shopper saw alongside it, newest first). Optional — an older client
    # or a wardrobe item with no search behind it simply sends nothing.
    distractor_options: dict[str, list[DistractorOption]] | None = None


class CreateMultiTryOnRequest(BaseModel):
    """One job per photo, same product/outfit/wardrobe item — e.g. front +
    back angles. Charged per job (2 photos = double the cost of one),
    checked upfront against the whole batch, not partially charged if a
    later one fails."""

    user_photo_ids: list[str]
    product_id: str | None = None
    outfit_id: str | None = None
    wardrobe_item_id: str | None = None
    distractor_options: dict[str, list[DistractorOption]] | None = None


class ResultPlacement(BaseModel):
    """One item on the finished photo. `box` is [x0, y0, x1, y1] in
    fractions of the image, so a client can label it at any size."""

    name: str
    product_id: str | None = None
    slot: str | None = None
    #: the retailer's own product photo, for the card beside the result
    image_url: str | None = None
    drawn: bool = False
    box: list[float] | None = None
    #: why `drawn` is False — None when it's True. A shopper who asks
    #: "where are my shoes" deserves an answer better than a silent
    #: "matched": whether nothing on the photo answered to where it
    #: goes, or the render itself failed and is worth simply retrying.
    reason: str | None = None


class TryOnResultOut(ORMModel):
    id: str
    image_url: str
    width: int | None
    height: int | None
    placements: list[ResultPlacement] | None = None


class TryOnJobOut(ORMModel):
    id: str
    status: JobStatus
    provider: str
    provider_model: str
    credit_cost: int
    error_message: str | None
    progress: str | None = None
    product: ProductOut | None
    outfit: OutfitOut | None
    wardrobe_item: WardrobeItemOut | None
    result: TryOnResultOut | None
    user_photo: UserPhotoOut
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    @model_validator(mode="after")
    def _labels_match_what_was_drawn(self) -> "TryOnJobOut":
        # A finished job's "on photo" labels follow what actually
        # happened, not a plan of what an engine was expected to draw:
        # drawn_by() predicts from the item list alone, so a product that
        # was attempted and failed — no region found, every retry missed
        # the quality bar and nothing shippable resulted — still counted
        # as "drawn" as long as the theoretical plan included its slot.
        # That produced "every item is on the photo" on a job where a
        # selected item genuinely wasn't. Real per-item results exist
        # (placements, from the same reports the quality pipeline already
        # verified each item against) whenever the render path computed
        # them; use those instead, and only fall back to the plan-based
        # guess for the paths that don't (whole-outfit engines, the
        # legacy per-layer chain) where no real per-item signal exists.
        if self.outfit is not None and self.status == JobStatus.COMPLETED:
            if self.result is not None and self.result.placements:
                self.outfit.drawn_from_placements(self.result.placements)
            else:
                self.outfit.drawn_by(self.provider, self.provider_model)
        return self
