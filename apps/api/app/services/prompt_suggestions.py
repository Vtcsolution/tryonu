"""Ready-to-tap stylist prompts built from a user's saved preferences —
the categories they picked in onboarding (see app/core/taxonomy.py), their
colours and styles. Pure string building, no LLM call: each phrase comes
from a taxonomy `search` phrase that is known to return real listings, and
every item word in it is one the stylist's search-term extraction
recognises, so tapping a suggestion searches for exactly what it says.
"""

from __future__ import annotations

from app.core.taxonomy import Node, feed_nodes
from app.models.preference import UserPreference

MAX_PROMPTS = 6

# category segment of a taxonomy id ("w.eastern.shalwar" -> "eastern")
_MAIN_CATEGORIES = {"eastern", "western", "girls", "boys", "baby"}
_EXTRA_ORDER = ("shoes", "jewellery", "bags", "watches", "accessories")
_AUDIENCE_WORD = {"w": "women", "m": "men"}
_DROP_WORDS = {"women", "men", "womens", "mens", "women's", "men's"}


def _phrase(node: Node) -> str:
    return " ".join(w for w in node.search.lower().split() if w not in _DROP_WORDS)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def suggest_prompts(pref: UserPreference | None) -> list[str]:
    if pref is None or not pref.preferred_categories:
        return []
    picks: list[Node] = []
    for node in feed_nodes(pref.preferred_categories):
        # a broad pick ("Western wear", "Jewellery") alone reads as a vague
        # prompt ("clothing") — suggest its first few concrete items instead
        picks.extend(node.children[:3] if node.id.count(".") == 1 and node.children else [node])
    if not picks:
        return []

    mains = [p for p in picks if p.id.split(".")[1] in _MAIN_CATEGORIES]
    extras_by_cat: dict[str, list[str]] = {}
    for p in picks:
        cat = p.id.split(".")[1]
        if cat in _EXTRA_ORDER:
            extras_by_cat.setdefault(cat, []).append(_phrase(p))
    # round-robin across categories so one prompt pairs shoes with jewellery
    # rather than three kinds of bangles
    extras: list[str] = []
    queues = [list(extras_by_cat[c]) for c in _EXTRA_ORDER if c in extras_by_cat]
    while any(queues):
        for q in queues:
            if q:
                extras.append(q.pop(0))

    audience = pref.gender.value if pref.gender and pref.gender.value in ("women", "men") else None
    if audience is None:
        audience = _AUDIENCE_WORD.get(picks[0].id.split(".")[0])  # kids phrases already say girls/boys/baby
    for_whom = f" for {audience}" if audience else ""

    colors = [c.strip().lower() for c in (pref.preferred_colors or []) if c and c.strip()]
    styles = [s.strip().lower() for s in (pref.preferred_styles or []) if s and s.strip()]

    prompts: list[str] = []

    def add(text: str) -> None:
        text = text[0].upper() + text[1:]
        if text not in prompts:
            prompts.append(text)

    if mains:
        for i in range(MAX_PROMPTS):
            main = _phrase(mains[i % len(mains)])
            color = colors[i % len(colors)] if colors and i % 3 != 2 else ""
            style = styles[i % len(styles)] if styles and i % 3 == 2 else ""
            descriptor = color or style
            head = f"{descriptor} {main}" if descriptor else main
            if extras:
                start = (i * 2) % len(extras)
                chosen = [extras[(start + k) % len(extras)] for k in range(min(2, len(extras)))]
                add(f"{head}{for_whom} with {_join(list(dict.fromkeys(chosen)))}")
            else:
                add(f"{head}{for_whom}")
    if len(extras) >= 2 and len(prompts) < MAX_PROMPTS:
        add(f"{_join(extras[:3])}{for_whom}")
    elif extras and not mains:
        for i, e in enumerate(extras[:MAX_PROMPTS]):
            color = colors[i % len(colors)] if colors else ""
            add(f"{color + ' ' if color else ''}{e}{for_whom}")

    return prompts[:MAX_PROMPTS]
