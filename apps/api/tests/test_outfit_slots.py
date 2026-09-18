"""Which outfit part a real retailer title is — decides what the try-on
draws on the photo. Titles here are the kind eBay actually returns."""

from __future__ import annotations

import pytest

from app.models.enums import OutfitSlot
from app.services.outfit_slots import render_plan, slot_for


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


_OUTFIT = [
    (OutfitSlot.SHOES, "Pakistani Men Peshawari Sandals (Kaptaan Chappal)"),
    (OutfitSlot.OUTERWEAR, "BLACK New Men Solid Tuxedo Suit Dress Vest Waistcoat"),
    (OutfitSlot.OTHER, "Pakistani Men's Shalwar Kameez, Indian Kurta Pajama"),
    (OutfitSlot.ACCESSORY, "Kundan Bangles Set"),
]


def test_tryon_max_draws_outfit_then_waistcoat_then_shoes():
    assert render_plan(_OUTFIT, "tryon-max") == [
        (2, OutfitSlot.DRESS),
        (1, OutfitSlot.OUTERWEAR),
        (0, OutfitSlot.SHOES),
    ]


def test_standard_model_draws_a_full_outfit_alone():
    """v1.6 can't layer or draw footwear — a waistcoat sent after the kameez
    replaced its top with a pasted patch."""
    assert render_plan(_OUTFIT, "tryon-v1.6") == [(2, OutfitSlot.DRESS)]


def test_standard_model_still_combines_separate_top_and_bottom():
    items = [(OutfitSlot.TOP, "Cotton kurta for men"), (OutfitSlot.BOTTOM, "Levi 501 jeans")]
    assert render_plan(items, "tryon-v1.6") == [(1, OutfitSlot.BOTTOM), (0, OutfitSlot.TOP)]


def test_each_layer_gets_an_explicit_category_or_instruction():
    from app.workers.tasks.tryon_tasks import _Layer, _tryon_input

    vest = _Layer("https://img.example/vest.jpg", OutfitSlot.OUTERWEAR)
    v16 = _tryon_input("https://img.example/me.jpg", vest, "tryon-v1.6")
    assert v16.category == "tops" and v16.prompt == ""
    mx = _tryon_input("https://img.example/me.jpg", vest, "tryon-max")
    assert "over the person's current outfit" in mx.prompt
    kameez = _tryon_input("https://img.example/me.jpg", _Layer("https://img.example/k.jpg", OutfitSlot.DRESS), "tryon-v1.6")
    assert kameez.category == "one-pieces"


def test_whole_outfit_render_includes_shoes_bag_and_every_piece_of_jewellery():
    items = [*_OUTFIT, (OutfitSlot.ACCESSORY, "Jhumka earrings"), (OutfitSlot.BAG, "Leather clutch")]
    assert render_plan(items, "gpt-image-1", whole_outfit=True) == [
        (2, OutfitSlot.DRESS),
        (1, OutfitSlot.OUTERWEAR),
        (0, OutfitSlot.SHOES),
        (3, OutfitSlot.ACCESSORY),
        (4, OutfitSlot.ACCESSORY),
        (5, OutfitSlot.BAG),
    ]
