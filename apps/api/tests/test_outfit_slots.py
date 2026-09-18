"""Which outfit part a real retailer title is — decides what the try-on
draws on the photo. Titles here are the kind eBay actually returns."""

from __future__ import annotations

import pytest

from app.models.enums import OutfitSlot
from app.services.outfit_slots import slot_for


@pytest.mark.parametrize(
    ("title", "slot"),
    [
        # real bug: rendered as an accessory, so the photo kept the jeans
        ("White Indian Cotton Kurta Pajama Men's Ethnic Wear, Pakistan Shalwar kameez", OutfitSlot.DRESS),
        ("Pakistani Indian salwar kameez Embroidered Chiffon Long Duppatta", OutfitSlot.DRESS),
        ("Khaadi Medium 3PC Lawn Suit", OutfitSlot.DRESS),
        ("Bridal lehenga choli red", OutfitSlot.DRESS),
        ("Men's Paisley Formal Tuxedo Vest Tie & Hankie set Wedding Prom", OutfitSlot.OUTERWEAR),
        ("Men waistcoat for shalwar kameez black", OutfitSlot.OUTERWEAR),
        ("South Asian Women's Mint Green Khussa Size 7.5", OutfitSlot.SHOES),
        ("Peshawari chappal handmade", OutfitSlot.SHOES),
        ("Jhumka earrings for saree wedding", OutfitSlot.ACCESSORY),
        ("Natural Stone Hematite Tiger Eye Energy Healing Bracelet", OutfitSlot.ACCESSORY),
        ("Cotton kurta for men", OutfitSlot.TOP),
        ("Levi 501 jeans", OutfitSlot.BOTTOM),
        ("Leather Bomber Jacket", OutfitSlot.OUTERWEAR),
        ("Something unnamed", OutfitSlot.OTHER),
    ],
)
def test_slot_for_real_titles(title, slot):
    assert slot_for(title) == slot
