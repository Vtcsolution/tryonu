"""Orders on a store's own page (tryonu.app/<store>): a customer's cart becomes
an order the store gets by email, with a ready WhatsApp message the customer
sends; the store follows them up in its dashboard (Orders)."""

from __future__ import annotations

import secrets
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.core.logging import logger
from app.core.rate_limit import rate_limiter
from app.models.store import Store, StoreProduct
from app.models.store_order import StoreOrder
from app.models.user import User
from app.services import store_service as svc

router = APIRouter(prefix="/stores", tags=["stores"])

STATUSES = ("new", "confirmed", "shipped", "delivered", "cancelled")
_STATUS_WORDS = {
    "confirmed": "confirmed your order",
    "shipped": "sent your order on its way",
    "delivered": "marked your order as delivered",
    "cancelled": "cancelled your order",
}


class OrderItemIn(BaseModel):
    product_id: str
    qty: int = Field(ge=1, le=20)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=40)
    email: EmailStr | None = None
    address: str = Field(min_length=5, max_length=1000)
    city: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class OrderPlacedOut(BaseModel):
    number: str
    total_cents: int
    currency: str
    # wa.me link with the whole order written out, to the store's WhatsApp; None without one
    whatsapp_url: str | None


class OrderOut(BaseModel):
    id: str
    number: str
    customer_name: str
    phone: str
    email: str | None
    address: str
    city: str | None
    note: str | None
    items: list[dict]
    total_cents: int
    currency: str
    status: str
    created_at: datetime


def _money(cents: int, currency: str) -> str:
    from app.services.looks_email import _money as fmt

    return fmt(cents, currency) or f"{cents / 100:,.2f} {currency.upper()}"


def _order_text(store: Store, order: StoreOrder) -> str:
    lines = [f"New order {order.number} for {store.name} (from tryonu.app/{store.slug})", ""]
    lines += [f"{it['qty']} x {it['name']}: {_money(it['price_cents'] * it['qty'], order.currency)}" for it in order.items]
    lines += ["", f"Total: {_money(order.total_cents, order.currency)}", "", f"Name: {order.customer_name}", f"Phone: {order.phone}"]
    if order.email:
        lines.append(f"Email: {order.email}")
    lines.append(f"Address: {order.address}{', ' + order.city if order.city else ''}")
    if order.note:
        lines.append(f"Note: {order.note}")
    return "\n".join(lines)


def _out(o: StoreOrder) -> OrderOut:
    return OrderOut(
        id=o.id, number=o.number, customer_name=o.customer_name, phone=o.phone, email=o.email, address=o.address,
        city=o.city, note=o.note, items=o.items, total_cents=o.total_cents, currency=o.currency, status=o.status,
        created_at=o.created_at,
    )


@router.post(
    "/public/{slug}/orders",
    response_model=OrderPlacedOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("store_order", limit=20, window_seconds=3600))],
)
async def place_order(slug: str, payload: OrderIn, db: DbSession, user: OptionalUser):
    """Prices come from the store's products as they are now, never from the page."""
    store = await db.scalar(select(Store).where(Store.slug == slug))
    if store is None or not svc.is_live(store):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    wanted: dict[str, int] = {}
    for it in payload.items:
        wanted[it.product_id] = min(20, wanted.get(it.product_id, 0) + it.qty)
    products = {
        p.id: p
        for p in (
            await db.execute(
                select(StoreProduct).where(
                    StoreProduct.store_id == store.id, StoreProduct.is_active.is_(True), StoreProduct.id.in_(list(wanted))
                )
            )
        ).scalars()
    }
    if len(products) != len(wanted):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some products in your cart aren't sold any more. Please check your cart.")
    currencies = {p.currency.lower() for p in products.values()}
    if len(currencies) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please order products with different currencies separately.")
    items = [
        {
            "product_id": pid,
            "name": products[pid].name[:200],
            "price_cents": products[pid].price_cents,
            "qty": qty,
            "image": svc.image_url(products[pid].images[0]) if products[pid].images else None,
        }
        for pid, qty in wanted.items()
    ]
    order = StoreOrder(
        store_id=store.id,
        number="TU-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6)),
        customer_name=payload.name.strip(),
        phone=payload.phone.strip(),
        email=str(payload.email) if payload.email else None,
        address=payload.address.strip(),
        city=(payload.city or "").strip() or None,
        note=(payload.note or "").strip() or None,
        items=items,
        total_cents=sum(it["price_cents"] * it["qty"] for it in items),
        currency=currencies.pop(),
        user_id=user.id if user else None,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    text = _order_text(store, order)
    await _tell_store(db, store, order, text)
    await _tell_customer(store, order)
    from app.services.team_alerts import tell_team

    tell_team("sales", f"order {order.number} at {store.name}", text.splitlines())
    return OrderPlacedOut(
        number=order.number,
        total_cents=order.total_cents,
        currency=order.currency,
        whatsapp_url=f"https://wa.me/{store.whatsapp}?text={quote(text)}" if store.whatsapp else None,
    )


async def _tell_store(db: DbSession, store: Store, order: StoreOrder, text: str) -> None:
    from app.email.registry import get_email_provider
    from app.email.templates import action_email, site_url

    to = store.contact_email or await db.scalar(select(User.email).where(User.id == store.owner_user_id))
    if not to:
        return
    lines = text.split("\n")[2:]
    mail = action_email(
        f"New order {order.number}",
        [line for line in lines if line.strip()],
        "Open my orders",
        site_url("/business#orders"),
        after=["Contact the customer to confirm, then mark the order in your dashboard."],
        footer=f"Order from your TryOnU store page: tryonu.app/{store.slug}",
    )
    try:
        await get_email_provider().send(
            to=to, subject=f"New order {order.number}: {_money(order.total_cents, order.currency)}", text_body=mail[0],
            html_body=mail[1], reply_to=order.email,
        )
    except Exception as exc:  # noqa: BLE001 - the order is saved and in the dashboard either way
        logger.warning("store_order_email_failed", order=order.number, error=str(exc)[:200])


async def _tell_customer(store: Store, order: StoreOrder, status_now: str | None = None) -> None:
    from app.email.registry import get_email_provider
    from app.email.templates import action_email, site_url

    if not order.email:
        return
    if status_now:
        heading = f"{store.name} {_STATUS_WORDS[status_now]}"
        lines = [f"Your order {order.number} is now: {status_now}."]
        subject = f"Your order {order.number}: {status_now}"
    else:
        heading = f"Thank you! {store.name} has your order"
        lines = [
            f"Your order number is {order.number}.",
            *[f"{it['qty']} x {it['name']}" for it in order.items],
            f"Total: {_money(order.total_cents, order.currency)}",
            f"{store.name} will contact you on {order.phone} to confirm delivery and payment.",
        ]
        subject = f"Your order {order.number} at {store.name}"
    mail = action_email(heading, lines, f"Visit {store.name}", site_url(f"/{store.slug}"),
                        footer=f"{store.name} sells on TryOnU. TryOnU doesn't take payment for store orders.")
    try:
        await get_email_provider().send(to=order.email, subject=subject, text_body=mail[0], html_body=mail[1])
    except Exception as exc:  # noqa: BLE001 - the order stands either way
        logger.warning("store_order_customer_email_failed", order=order.number, error=str(exc)[:200])


async def _my_store(db: DbSession, me: User) -> Store:
    store = await db.scalar(select(Store).where(Store.owner_user_id == me.id))
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You don't have a store yet")
    return store


class OrdersOut(BaseModel):
    items: list[OrderOut]
    new: int


@router.get("/me/orders", response_model=OrdersOut)
async def my_orders(me: CurrentUser, db: DbSession, show: str = "all"):
    store = await _my_store(db, me)
    stmt = select(StoreOrder).where(StoreOrder.store_id == store.id)
    if show in STATUSES:
        stmt = stmt.where(StoreOrder.status == show)
    rows = (await db.execute(stmt.order_by(StoreOrder.created_at.desc()).limit(200))).scalars().all()
    new = int(await db.scalar(select(func.count()).select_from(StoreOrder).where(StoreOrder.store_id == store.id, StoreOrder.status == "new")) or 0)
    return OrdersOut(items=[_out(o) for o in rows], new=new)


class OrderStatusIn(BaseModel):
    status: str = Field(pattern="^(" + "|".join(STATUSES) + ")$")


@router.patch("/me/orders/{order_id}", response_model=OrderOut)
async def update_order(order_id: str, payload: OrderStatusIn, me: CurrentUser, db: DbSession):
    store = await _my_store(db, me)
    order = await db.scalar(select(StoreOrder).where(StoreOrder.id == order_id, StoreOrder.store_id == store.id))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    changed = order.status != payload.status
    order.status = payload.status
    await db.commit()
    await db.refresh(order)
    if changed and payload.status in _STATUS_WORDS:
        await _tell_customer(store, order, payload.status)
    return _out(order)
