"""The website in the visitor's own language, where English isn't widely used.

Only countries where people really prefer their own language get it (Saudi
Arabia: Arabic, Japan: Japanese...), always with a button back to English.
Pakistan, India and other English-using countries stay in English.

The page's text is sent here in small batches; each piece is translated once
by the AI and kept in the translations table, so the same text is never paid
for twice."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.translation import Translation

# language: (its own name, writes right to left)
LANGUAGES: dict[str, tuple[str, bool]] = {
    "ar": ("العربية", True),
    "ja": ("日本語", False),
    "zh": ("中文", False),
    "ko": ("한국어", False),
    "fr": ("Français", False),
    "de": ("Deutsch", False),
    "es": ("Español", False),
    "pt": ("Português", False),
    "it": ("Italiano", False),
    "tr": ("Türkçe", False),
    "ru": ("Русский", False),
    "id": ("Bahasa Indonesia", False),
    "vi": ("Tiếng Việt", False),
    "th": ("ไทย", False),
    "pl": ("Polski", False),
}
ENGLISH_NAMES = {
    "ar": "Arabic", "ja": "Japanese", "zh": "Simplified Chinese", "ko": "Korean", "fr": "French", "de": "German",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian", "tr": "Turkish", "ru": "Russian", "id": "Indonesian",
    "vi": "Vietnamese", "th": "Thai", "pl": "Polish",
}
# only where the local language is what people expect; every other country: English
_COUNTRY_LANG: dict[str, str] = {
    **dict.fromkeys(
        "SA AE QA KW BH OM EG JO LB IQ SY YE LY DZ MA TN SD PS MR".split(), "ar"
    ),
    "JP": "ja",
    "CN": "zh",
    "TW": "zh",
    "KR": "ko",
    **dict.fromkeys("FR MC SN CI CM ML BF NE GN BJ TG GA CG CD MG".split(), "fr"),
    **dict.fromkeys("DE AT".split(), "de"),
    **dict.fromkeys("ES MX AR CO CL PE VE EC GT CU BO DO HN PY SV NI CR PA UY".split(), "es"),
    **dict.fromkeys("BR PT AO MZ".split(), "pt"),
    "IT": "it",
    "TR": "tr",
    **dict.fromkeys("RU BY".split(), "ru"),
    "ID": "id",
    "VN": "vi",
    "TH": "th",
    "PL": "pl",
}
MAX_TEXTS = 80
MAX_CHARS = 1200


def language_for(country: str | None) -> str:
    return _COUNTRY_LANG.get((country or "").upper(), "en")


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


_INSTRUCTIONS = (
    "You translate the text of TryOnU, a fashion website where people try clothes on their own photo before "
    "buying, from English into {language}. Translate each string in the list, in the same order, in a natural, "
    "friendly shopping tone, as short as the English. Keep exactly as they are: the name TryOnU, brand and shop "
    "names, prices and numbers, @usernames, web addresses, emoji and anything in curly braces like {{name}}. "
    'Answer with JSON: {{"t": [the translated strings, one per input string]}}.'
)


async def translate(db: AsyncSession, lang: str, texts: list[str]) -> list[str]:
    """The texts in `lang`: from the kept translations, the rest translated now
    (in one AI call) and kept. Anything that can't be translated stays English."""
    if lang not in LANGUAGES or not texts:
        return texts
    keys = [_key(t) for t in texts]
    known = {
        row.key: row.text
        for row in (await db.execute(select(Translation).where(Translation.lang == lang, Translation.key.in_(set(keys))))).scalars()
    }
    missing = list(dict.fromkeys(t for t, k in zip(texts, keys) if k not in known))
    if missing:
        made = await _ask(lang, missing)
        for source, text in zip(missing, made):
            if text and text != source:
                known[_key(source)] = text
                db.add(Translation(lang=lang, key=_key(source), source=source, text=text))
        try:
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - another visitor kept the same text at the same moment
            await db.rollback()
            logger.info("translation_save_race", error=str(exc)[:120])
    return [known.get(k, t) for t, k in zip(texts, keys)]


async def _ask(lang: str, texts: list[str]) -> list[str]:
    from app.services.tryon_quality.vision import VisionError, ask_json

    try:
        answer = await ask_json(
            _INSTRUCTIONS.format(language=ENGLISH_NAMES[lang]),
            [{"type": "text", "text": json.dumps(texts, ensure_ascii=False)}],
            timeout=60.0,
        )
    except VisionError as exc:
        logger.warning("translate_failed", lang=lang, error=str(exc)[:200])
        return texts
    out = answer.get("t") if isinstance(answer, dict) else None
    if not isinstance(out, list) or len(out) != len(texts):
        logger.warning("translate_bad_answer", lang=lang, got=len(out) if isinstance(out, list) else None, wanted=len(texts))
        return texts
    return [str(x) if isinstance(x, str) and x.strip() else src for x, src in zip(out, texts)]
