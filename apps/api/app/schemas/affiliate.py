from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import AffiliateSource


class RecordClickRequest(BaseModel):
    product_id: str
    source: AffiliateSource = AffiliateSource.PRODUCT_CARD
    session_id: str | None = None


class RecordClickResponse(BaseModel):
    redirect_url: str
