"""Understands whatever a shopper types: spelling mistakes, other languages,
mixed Urdu and English, or just an occasion ("something smart for my cousin's
engagement"). Turns it into the short English product searches the shops
understand. One small AI call per new sentence, kept in memory; when the AI
can't answer, the word-matching in stylist_service takes over."""

from __future__ import annotations

import json
import re

from app.core.logging import logger

_INSTRUCTIONS = (
    "You read what a shopper typed on a fashion try-on website and list the products to search for in online shops. "
    "They may write in any language, with spelling mistakes, in very few words. Reply with JSON only: "
    '{"fashion": true|false, "for": "men"|"women"|null, "items": ["search", ...]}. '
    "fashion: false only when it isn't about clothes, shoes, bags, jewellery or accessories at all. "
    "for: only when they say who it is for (\"for my wife\", \"a boy\"), otherwise null. "
    "items: one entry per product, in the order they named them, each 1 to 5 plain English words ending with the product "
    "type, with the colour, material and style they asked for, like \"black leather jacket\" or \"gold jhumka earrings\". "
    "Correct the spelling. Keep brand names. Never add a colour, material or brand they didn't ask for, and never add a "
    "product they didn't name, and leave out anything they say they don't want. "
    "Only when they name no product at all, just an occasion or a style, suggest a simple complete outfit: 3 or 4 clothing "
    "pieces and shoes that suit it, with no jewellery, watch, bag or other accessory unless they asked for one."
)
_CLEAN = re.compile(r"[^a-z0-9 ]+")
_cache: dict[str, dict] = {}


async def _ask_ai(prompt: str) -> dict | None:
    from app.services.tryon_quality.vision import VisionError, ask_json

    try:
        return await ask_json(_INSTRUCTIONS, [{"type": "text", "text": json.dumps(prompt, ensure_ascii=False)}], timeout=15.0)
    except VisionError as exc:
        logger.info("prompt_reader_unavailable", error=str(exc)[:160])
        return None


async def read_prompt(prompt: str) -> dict | None:
    """{"fashion": bool, "for": "men"|"women"|None, "items": [searches]}, or None when it can't be told."""
    key = " ".join(prompt.lower().split())[:500]
    if key in _cache:
        return _cache[key]
    answer = await _ask_ai(prompt[:500])
    if not isinstance(answer, dict) or not isinstance(answer.get("items"), list):
        return None
    items: list[str] = []
    for raw in answer["items"]:
        words = _CLEAN.sub(" ", str(raw).lower().replace("-", " ")).split()
        if 1 <= len(words) <= 6:
            items.append(" ".join(words))
    who = answer.get("for")
    read = {
        "fashion": answer.get("fashion") is not False,
        "for": who if who in ("men", "women") else None,
        "items": list(dict.fromkeys(items)),
    }
    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = read
    return read
