"""The look board: one image built from several product photos. Offline."""

from __future__ import annotations

import io

from PIL import Image

from app.services.tryon_direct.look_board import BoardItem, build_look_board, label_for
from tests.fashn_fakes import image_bytes


def test_labels_name_what_each_product_is():
    assert label_for("Indian Gold Plated Jhumka Earrings Pearl", False) == "Earrings"
    assert label_for("Opal Flower Nose Pin 18k", False) == "Nose ring"
    assert label_for("Tucnoeu 8 Pcs Dangle Nose Rings Hoop for Women", False) == "Nose ring"
    assert label_for("Vintage Style Gold Bracelet Watch Women Square", False) == "Watch"
    assert label_for("Kundan Gold Maang Tikka", False) == "Maang tikka"
    assert label_for("Gold Black Rhinestone Choker Necklace", False) == "Necklace"
    assert label_for("Size 7 Multi Strand Dome Statement Ring", False) == "Ring"
    assert label_for("Designer Georgette Lehenga Choli", True) == "Outfit"
    assert label_for("Pink Embroidered Lehenga Choli with Dupatta", True) == "Outfit"


def test_every_product_is_on_the_board_even_when_cutout_fails(monkeypatch):
    def no_cutout(*_a, **_kw):  # noqa: ANN002, ANN003
        raise RuntimeError("cutout unavailable")

    monkeypatch.setattr("app.services.tryon_quality.cutout.product_cutout_mask", no_cutout)
    items = [
        BoardItem(image_bytes((600, 900), (200, 30, 40)), "u1", "Red Dress", True),
        BoardItem(image_bytes((400, 400), (20, 20, 200)), "u2", "Blue Earrings", False),
        BoardItem(image_bytes((400, 400), (20, 160, 20)), "u3", "Green Bag", False),
    ]
    board, labels = build_look_board(items)
    img = Image.open(io.BytesIO(board)).convert("RGB")
    assert img.size == (1536, 2048)
    assert labels == ["Outfit", "Earrings", "Bag"]
    colours = set(img.getdata())
    for colour in ((200, 30, 40), (20, 20, 200), (20, 160, 20)):
        assert any(all(abs(a - b) <= 4 for a, b in zip(px, colour)) for px in colours)  # each product is drawn


def test_a_garment_worn_by_a_model_goes_on_the_board_without_her_head(monkeypatch):
    # Live: the model's face and skin on the board shifted the customer's skin tone.
    from app.services.tryon_direct import look_board

    monkeypatch.setattr(look_board, "_below_the_head", lambda bgr: 300)

    def no_cutout(*_a, **_kw):  # noqa: ANN002, ANN003
        raise RuntimeError("cutout unavailable")

    monkeypatch.setattr("app.services.tryon_quality.cutout.product_cutout_mask", no_cutout)
    photo = image_bytes((600, 900), (200, 30, 40))
    worn = look_board._cut_out(BoardItem(photo, "u1", "Pink Lehenga", True))
    jewel = look_board._cut_out(BoardItem(photo, "u2", "Gold Earrings", False))
    assert worn.size == (600, 600)  # rows above the chin dropped
    assert jewel.size == (600, 900)  # jewellery photos are never cut


def test_a_hand_holding_an_accessory_is_left_off_the_board(monkeypatch):
    # Live: the clutch photo's red-nailed hand came back holding the clutch.
    import numpy as np

    from app.services.tryon_direct import look_board

    bgr = np.full((400, 600, 3), 255, np.uint8)
    bgr[100:300, 100:500] = (40, 180, 220)  # the bag
    bgr[250:400, 0:180] = (120, 150, 220)  # a hand over its lower-left corner, off the frame
    mask = np.zeros((400, 600), np.uint8)
    mask[100:300, 100:500] = 255
    mask[250:400, 0:180] = 255
    hand = np.zeros((400, 600), np.uint8)
    hand[250:400, 0:180] = 255
    monkeypatch.setattr("app.services.tryon_quality.cutout.person_mask", lambda img, url: hand)

    out, cut = look_board._without_people(bgr, BoardItem(b"", "u", "Gold Clutch Bag", False), mask, 0)
    assert cut[390, 10] == 0  # the hand outside the bag is gone
    assert cut[255, 175] == 255 and tuple(out[255, 175]) == (40, 180, 220)  # the covered corner is bag again

    earring_on_ear = np.full((400, 600), 255, np.uint8)  # the person would take everything with them
    monkeypatch.setattr("app.services.tryon_quality.cutout.person_mask", lambda img, url: earring_on_ear)
    _, untouched = look_board._without_people(bgr, BoardItem(b"", "u", "Gold Earrings", False), mask, 0)
    assert (untouched == mask).all()
