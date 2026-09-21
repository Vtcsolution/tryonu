"""A shopper is never shown the other gender's listings.

Live results come from retailers that match words, not shoppers: a search
for "men leather ankle boots" came back with women's red pumps, and those
were offered as the alternatives under a man's boot."""

from __future__ import annotations

from app.services.gender_filter import gender_of, keep_for_gender


def test_reads_the_gender_out_of_a_listing_title():
    assert gender_of("Reaction Women's Brown Leather Boots") == "women"
    assert gender_of("Ladies Platform Heels") == "women"
    assert gender_of("Men's Leather Ankle Boots") == "men"
    assert gender_of("Gents Formal Shoes") == "men"


def test_a_title_that_names_nobody_or_everybody_has_no_gender():
    assert gender_of("Leather Chelsea Boots UK 9") is None
    assert gender_of("Unisex Silver Bracelet") is None
    assert gender_of("Men Women Couple Matching Rings") is None
    # "women" contains "men" — the word boundary has to hold
    assert gender_of("Womens Chappal") == "women"


def test_only_the_other_gender_is_dropped():
    titles = [
        "Men's Leather Ankle Boots",
        "Reaction Women's Brown Leather Boots",
        "Pleaser Ladies Platform Heels",
        "Leather Chelsea Boots UK 9",
        "Unisex Rain Boots",
    ]
    for_him = keep_for_gender(titles, "men")
    assert for_him == ["Men's Leather Ankle Boots", "Leather Chelsea Boots UK 9", "Unisex Rain Boots"]
    for_her = keep_for_gender(titles, "women")
    assert for_her[:2] == ["Reaction Women's Brown Leather Boots", "Pleaser Ladies Platform Heels"]


def test_nothing_is_filtered_without_a_gender_to_filter_for():
    titles = ["Men's Boots", "Women's Boots"]
    assert keep_for_gender(titles, None) == titles
    assert keep_for_gender(titles, "unisex") == titles
    assert keep_for_gender(titles, "kids") == titles


def test_a_shopper_is_never_left_with_nothing():
    """An empty shelf is worse than a mixed one: if every listing the
    retailer returned is the other gender's, show them anyway rather than
    telling him there are no boots."""
    only_hers = ["Women's Ankle Boots", "Ladies Chelsea Boots"]
    assert keep_for_gender(only_hers, "men") == only_hers


def test_it_reads_the_title_off_whatever_object_it_is_given():
    class Listing:
        def __init__(self, name):
            self.name = name

    items = [Listing("Men's Watch"), Listing("Women's Watch")]
    kept = keep_for_gender(items, "men", lambda i: i.name)
    assert [i.name for i in kept] == ["Men's Watch"]
