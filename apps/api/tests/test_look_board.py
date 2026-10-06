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
