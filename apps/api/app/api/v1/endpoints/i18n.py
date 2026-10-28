"""The website in the visitor's language: which one (from their country), and
the page's text translated (made once, kept)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import DbSession
from app.core.rate_limit import rate_limiter
from app.services import translate_service as svc
from app.services.shopper_context import current_country

router = APIRouter(prefix="/i18n", tags=["i18n"])


class LocaleOut(BaseModel):
    country: str | None
    lang: str  # "en", or the language this country prefers
    name: str | None  # that language in its own words ("العربية")
    rtl: bool


@router.get("/locale", response_model=LocaleOut)
async def locale():
    country = current_country()
    lang = svc.language_for(country)
    name, rtl = svc.LANGUAGES.get(lang, (None, False))
    return LocaleOut(country=country, lang=lang, name=name, rtl=rtl)


class TranslateIn(BaseModel):
    lang: str = Field(max_length=8)
    texts: list[str] = Field(max_length=svc.MAX_TEXTS)


@router.post("/translate", dependencies=[Depends(rate_limiter("i18n_translate", limit=900, window_seconds=3600))])
async def translate(payload: TranslateIn, db: DbSession):
    if payload.lang not in svc.LANGUAGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That language isn't offered.")
    texts = [t[: svc.MAX_CHARS] for t in payload.texts]
    return {"lang": payload.lang, "texts": await svc.translate(db, payload.lang, texts)}
