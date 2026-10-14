from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import delete, select

from app.models.admitad_feed import AdmitadFeedItem
from app.models.store import Store, StoreProduct
from app.models.user import User
from app.scripts.sample_store_products import add_samples, remove_samples
from app.services import store_service as svc

_WORDS = ["Silk Dress", "Gold Earrings", "Leather Handbag", "Pearl Necklace", "Strap Sandals",
          "Steel Watch", "Wool Scarf", "Block Heels", "Cotton Kurta", "Charm Bracelet", "Mini Skirt", "Crop Top"]
# what the first version picked on the live catalogue: never again
_JUNK = ["Bolsos Hf Vaso de Plastico Flamenco 260 Ml", "Juego de destornilladores tipo relojero",
         "Recambio Espaciador Rodamiento Grande Pedal (Wheels)", "Halloween Ghost Pumpkin Acrylic Earrings",
         "Eurocarnavales 6 Vasos Celestes con Topos Blancos"]


async def _store(db, *, limit=50):  # noqa: ANN001, ANN202
    user = User(email=f"shop-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
    db.add(user)
    await db.flush()
    store = Store(owner_user_id=user.id, name="Sample Shop", slug=f"sample-{uuid.uuid4().hex[:8]}", country="GB",
                  status="approved", plan_code="basic", plan_product_limit=limit,
                  plan_expires_at=svc.utcnow() + timedelta(days=30))
    db.add(store)
    await db.commit()
    return store


async def _catalogue(db):  # noqa: ANN001, ANN202
    await db.execute(delete(AdmitadFeedItem).where(AdmitadFeedItem.campaign_id == 999001))
    for i, name in enumerate(_WORDS + _JUNK):
        db.add(AdmitadFeedItem(campaign_id=999001, campaign_name="Test shop", offer_id=f"o{i}", name=name,
                               price_cents=1000 + i, currency="EUR", image_url=f"https://img.example.com/{i}.jpg",
                               product_url=f"https://shop.example.com/{i}", available=True))
    await db.commit()


async def test_adds_ten_real_products_once_and_removes_only_those(db):  # noqa: ANN001
    await _catalogue(db)
    store = await _store(db)
    own = StoreProduct(store_id=store.id, external_id="mine-1", name="My own lehenga", price_cents=5000,
                       images=["https://x.example.com/a.jpg"], product_url="https://x.example.com/a")
    db.add(own)
    await db.commit()

    added = await add_samples(db, store)
    assert len(added) == 10
    rows = (await db.execute(select(StoreProduct).where(StoreProduct.store_id == store.id))).scalars().all()
    samples = [p for p in rows if p.external_id.startswith("sample-")]
    assert len(samples) == 10 and all(p.images and p.currency in ("usd", "eur", "gbp") and p.is_active for p in samples)
    assert not {p.name for p in samples} & set(_JUNK)

    again = await add_samples(db, store)
    assert not set(again) & {p.name for p in samples}  # never the same product twice

    removed = await remove_samples(db, store)
    assert removed >= 10
    left = (await db.execute(select(StoreProduct).where(StoreProduct.store_id == store.id))).scalars().all()
    assert [p.external_id for p in left] == ["mine-1"]


async def test_stays_within_the_plan_limit(db):  # noqa: ANN001
    await _catalogue(db)
    store = await _store(db, limit=3)
    assert len(await add_samples(db, store)) == 3
