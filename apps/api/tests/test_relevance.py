"""Results have to be what the shopper asked for.

Live: "khussa shoes" came back from one retailer as men's sneakers and
gladiator sandals, and "maang tikka" as bracelets — real listings, none
of them the thing asked for.
"""

from __future__ import annotations

from app.services.relevance import distinctive, keep_relevant


def test_category_words_alone_cannot_carry_a_query():
    """"shoes" matches nearly every shoe; "khussa" is the ask."""
    assert distinctive("khussa shoes") == {"khussa"}
    assert distinctive("women analog watch") == {"analog"}
    assert distinctive("embroidered lawn shalwar kameez") == {"embroidered", "lawn", "shalwar", "kameez"}
    assert distinctive("women shoes") == set()  # nothing to pin down


def test_the_sneakers_that_came_back_for_khussa_are_dropped():
    listings = [
        "Beautifully embroidered black Khussa designed to complete your look",
        "Men Shoes Sneakers Breathable Running Shoes 2024 Men Sports Shoes",
        "Indian Punjabi Pakistani Ethnic Traditional Women Khussa Flat Shoes",
        "Summer Sandals Women Shoes Sexy Golden Sandals Woman Gladiator",
        "Khussai Yellow Peacock Floral Khussa Jutti Flats Pakistani",
    ]
    kept = keep_relevant(listings, "khussa shoes")
    assert all("khussa" in k.lower() for k in kept)
    assert len(kept) == 3


def test_the_bracelets_that_came_back_for_maang_tikka_are_dropped():
    listings = [
        "Indian Bridal Jewelry Set Gold Tone Necklace Earrings Maang Tikka Kundan",
        "Bohemian Style Multi-layer Alloy Bracelet Set Decorative Accessories",
        "Indian Luxury Kundan Choker Necklace Set Earrings Maang Tikka Bridal",
        "Holyfun Glossy 18K Gold Plated Stainless Steel Bangle Bracelet for Women",
        "Oxidized Silver Chandbali Earrings Maang Tikka Set Kundan Indian",
    ]
    kept = keep_relevant(listings, "maang tikka")
    assert all("tikka" in k.lower() for k in kept)


def test_one_distinctive_word_is_enough():
    """A listing needn't repeat the whole query: "Earrings Tikka Paste" is
    a maang tikka even without the word "maang"."""
    assert keep_relevant(
        ["Gold Tone Necklace Earrings Tikka Paste Set", "Plain Steel Bangle", "Tikka Set Kundan", "Tikka Gold"],
        "maang tikka",
    ) == ["Gold Tone Necklace Earrings Tikka Paste Set", "Tikka Set Kundan", "Tikka Gold"]


def test_a_query_of_only_category_words_keeps_everything():
    """With nothing distinctive to check, filtering would just be guessing."""
    listings = ["Women Running Shoes", "Ladies Leather Boots", "Sandals for Women"]
    assert keep_relevant(listings, "women shoes") == listings


def test_a_shelf_is_never_emptied():
    """An empty page is worse than a loose one: the shopper can judge for
    themselves, and a thin match is still a product."""
    listings = ["Plain Cotton Kurta", "Silk Saree Red", "Denim Jacket"]
    kept = keep_relevant(listings, "peshawari chappal")
    assert kept == listings


def test_near_misses_follow_the_real_matches_rather_than_replacing_them():
    listings = ["Handmade Peshawari Chappal Leather", "Plain Cotton Kurta", "Silk Saree", "Denim Jacket"]
    kept = keep_relevant(listings, "peshawari chappal", keep_at_least=3)
    assert kept[0] == "Handmade Peshawari Chappal Leather"
    assert len(kept) == 3  # the one real match, then the nearest fillers


def test_it_reads_the_title_off_whatever_it_is_given():
    class Listing:
        def __init__(self, name):
            self.name = name

    items = [Listing("Khussa Jutti Handmade"), Listing("Running Sneakers")]
    kept = keep_relevant(items, "khussa shoes", title=lambda i: i.name, keep_at_least=1)
    assert [i.name for i in kept] == ["Khussa Jutti Handmade"]
