"""Your size: a member's measurements turned into the size to pick.

Measurements (bust/chest, waist, hips) are matched against common size
charts and the largest of them wins, because a garment has to fit everywhere.
With only height and weight, a body-mass estimate is used instead, which is
rougher and is said so. The answer always comes with "check the shop's size
chart": shops cut differently, and this is a starting point, not a promise."""

from __future__ import annotations

from dataclasses import asdict, dataclass

LETTERS = ["XS", "S", "M", "L", "XL", "XXL", "3XL"]

# upper bounds in cm for XS..XXL (above the last: 3XL)
_WOMEN = {"bust": [82, 88, 94, 100, 108, 116], "waist": [64, 70, 76, 82, 90, 98], "hips": [90, 96, 102, 108, 116, 124]}
_MEN = {"bust": [88, 96, 104, 112, 120, 128], "waist": [74, 82, 90, 98, 106, 114], "hips": [90, 98, 106, 114, 122, 130]}
# body-mass index upper bounds for XS..XXL, when only height and weight are known
_BMI = {"women": [18.5, 21.0, 23.5, 26.5, 29.5, 33.0], "men": [19.5, 22.0, 24.5, 27.5, 30.5, 34.0]}

_WOMEN_NUMBERS = {  # letter: (UK, US, EU)
    "XS": ("6", "2", "34"), "S": ("8–10", "4–6", "36–38"), "M": ("12", "8", "40"), "L": ("14–16", "10–12", "42–44"),
    "XL": ("18", "14", "46"), "XXL": ("20", "16", "48"), "3XL": ("22", "18", "50"),
}
_MEN_NUMBERS = {  # letter: (chest in inches, EU, trousers waist in inches)
    "XS": ("34", "44", "28"), "S": ("36", "46", "30"), "M": ("38–40", "48–50", "32"), "L": ("42", "52", "34"),
    "XL": ("44–46", "54–56", "36–38"), "XXL": ("48–50", "58", "40"), "3XL": ("52", "60", "42–44"),
}


@dataclass
class SizeSuggestion:
    audience: str  # women | men
    letter: str
    uk: str | None
    us: str | None
    eu: str | None
    chest_in: str | None  # men's jackets and shirts
    trousers_waist_in: str | None
    shoe: dict | None  # {"eu": "39", "uk": "6", "us": "8"}
    basis: str  # measurements | height_weight
    fit: str

    def as_dict(self) -> dict:
        return asdict(self)


def _band(value: float, bounds: list[float]) -> int:
    for i, top in enumerate(bounds):
        if value < top:
            return i
    return len(bounds)


def _half(x: float) -> str:
    v = round(x * 2) / 2
    return str(int(v)) if v == int(v) else str(v)


def shoe_sizes(eu: int, audience: str) -> dict:
    uk = eu - (34 if audience == "men" else 33)
    us = uk + (1 if audience == "men" else 2)
    return {"eu": str(eu), "uk": _half(uk), "us": _half(us)}


def suggest(
    *,
    gender: str | None,
    height_cm: int | None = None,
    weight_kg: int | None = None,
    bust_cm: int | None = None,
    waist_cm: int | None = None,
    hips_cm: int | None = None,
    shoe_eu: int | None = None,
    fit: str | None = None,
) -> SizeSuggestion | None:
    audience = "men" if gender == "men" else "women"
    chart = _MEN if audience == "men" else _WOMEN
    bands = [_band(v, chart[k]) for k, v in (("bust", bust_cm), ("waist", waist_cm), ("hips", hips_cm)) if v]
    if bands:
        index, basis = max(bands), "measurements"
    elif height_cm and weight_kg and 100 <= height_cm <= 230 and 25 <= weight_kg <= 250:
        bmi = weight_kg / ((height_cm / 100) ** 2)
        index, basis = _band(bmi, _BMI[audience]), "height_weight"
        tall = height_cm >= (185 if audience == "men" else 175)
        if tall and index < 2:  # long arms and legs need the length of an M at least
            index = 2
    elif shoe_eu:
        index, basis = -1, "shoes_only"
    else:
        return None
    fit = fit if fit in ("loose", "slim") else "regular"
    if index >= 0 and fit == "loose":
        index = min(index + 1, len(LETTERS) - 1)
    letter = LETTERS[index] if index >= 0 else ""
    uk = us = eu = chest = waist_in = None
    if letter and audience == "women":
        uk, us, eu = _WOMEN_NUMBERS[letter]
    elif letter:
        chest, eu, waist_in = _MEN_NUMBERS[letter]
        if waist_cm:
            waist_in = str(round(waist_cm / 2.54))
    return SizeSuggestion(
        audience=audience, letter=letter, uk=uk, us=us, eu=eu, chest_in=chest, trousers_waist_in=waist_in,
        shoe=shoe_sizes(shoe_eu, audience) if shoe_eu else None, basis=basis, fit=fit,
    )
