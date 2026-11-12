"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { ProductCard } from "@/components/product/ProductCard";
import { formatPrice } from "@/components/try/shop";
import { Button } from "@/components/ui/Button";
import { WHATSAPP_GREEN, WhatsAppIcon } from "@/components/whatsapp/WhatsApp";
import { ApiError, relayedImageUrl } from "@/lib/api/client";
import { stores as storesApi } from "@/lib/api/endpoints";
import type { PublicStore, StoreProduct } from "@/lib/api/types";
import { useCart } from "./useCart";
import { waLink } from "./StoreShell";

/** "Try it on": picks the product to try on with the others picked (the bar at the bottom opens them on TryOnU). */
function useTryOn(slug: string) {
  return useCart(slug, "try");
}

function Grid({ store, products }: { store: PublicStore; products: StoreProduct[] }) {
  const cart = useCart(store.slug);
  const tryOn = useTryOn(store.slug);
  const [added, setAdded] = useState<string | null>(null);
  return (
    <>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {products.map((p) => (
          <div key={p.id} className="flex flex-col">
            <Link href={`/${store.slug}/products/${p.id}`} className="block">
              <ProductCard image={p.images[0]} name={p.name} priceCents={p.price_cents} currency={p.currency} label={p.category} />
            </Link>
            <div className="mt-2 grid gap-2">
              <Button
                size="sm"
                onClick={() => {
                  cart.add(p.id);
                  setAdded(p.id);
                }}
              >
                {added === p.id ? "Added to cart" : "Add to cart"}
              </Button>
              <Button size="sm" variant={tryOn.has(p.id) ? "primary" : "outline"} onClick={() => tryOn.toggle(p.id)}>
                {tryOn.has(p.id) ? "Picked to try on" : "Try it on"}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export function StoreHome({ store }: { store: PublicStore }) {
  const featured = store.products.filter((p) => p.is_featured);
  const shown = (featured.length ? [...featured, ...store.products.filter((p) => !p.is_featured)] : store.products).slice(0, 12);
  return (
    <div className="mx-auto tu-container py-8 md:py-12">
      <section className="rounded-[28px] border border-line bg-surface p-6 md:p-10">
        <h1 translate="no" className="notranslate font-display text-[clamp(30px,5vw,48px)] leading-tight text-ink">{store.name}</h1>
        {store.description && <p className="mt-3 max-w-2xl text-[16.5px] leading-relaxed text-ink-soft">{store.description}</p>}
        <p className="mt-3 text-[15px] text-muted">Try any product on your own photo before you buy.</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button href={`/${store.slug}/products`} size="md">
            Shop all {store.products.length} products <span aria-hidden="true">→</span>
          </Button>
          {store.whatsapp && (
            <a
              href={waLink(store.whatsapp, `Hi ${store.name}, I'm on your TryOnU store.`)}
              target="_blank"
              rel="noopener"
              style={{ backgroundColor: WHATSAPP_GREEN }}
              className="inline-flex min-h-[44px] items-center gap-2 rounded-full px-5 text-[15px] font-semibold text-white"
            >
              <WhatsAppIcon size={18} /> WhatsApp us
            </a>
          )}
        </div>
      </section>
      <h2 className="mt-10 font-display text-[26px] text-ink">{featured.length ? "Our picks" : "New in"}</h2>
      <div className="mt-4">
        <Grid store={store} products={shown} />
      </div>
      {store.products.length > shown.length && (
        <div className="mt-8 text-center">
          <Button href={`/${store.slug}/products`} variant="outline" size="md">
            See all products
          </Button>
        </div>
      )}
    </div>
  );
}

export function StoreProducts({ store }: { store: PublicStore }) {
  const [category, setCategory] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const categories = useMemo(() => [...new Set(store.products.map((p) => p.category).filter(Boolean))] as string[], [store.products]);
  const shown = store.products.filter(
    (p) => (!category || p.category === category) && (!q.trim() || p.name.toLowerCase().includes(q.trim().toLowerCase())),
  );
  return (
    <div className="mx-auto tu-container py-8 md:py-12">
      <h1 className="font-display text-[34px] text-ink">All products</h1>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search this store"
        aria-label="Search this store"
        className="mt-4 h-12 w-full max-w-md rounded-full border border-line-strong bg-surface px-4 text-[15.5px] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25"
      />
      {categories.length > 1 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {[null, ...categories].map((c) => (
            <button
              key={c ?? "all"}
              type="button"
              aria-pressed={category === c}
              onClick={() => setCategory(c)}
              className={`min-h-[38px] rounded-full border px-4 text-[14.5px] font-medium ${
                category === c ? "border-sage bg-sage text-white" : "border-line-strong text-ink hover:border-sage"
              }`}
            >
              {c ?? "All"}
            </button>
          ))}
        </div>
      )}
      <p className="mt-4 text-[14.5px] text-muted">{shown.length} products</p>
      <div className="mt-3">
        <Grid store={store} products={shown} />
      </div>
    </div>
  );
}

export function StoreProductPage({ store, productId }: { store: PublicStore; productId: string }) {
  const p = store.products.find((x) => x.id === productId);
  const cart = useCart(store.slug);
  const tryOn = useTryOn(store.slug);
  const router = useRouter();
  const [photo, setPhoto] = useState(0);
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);
  if (!p) {
    return (
      <div className="mx-auto tu-container py-20 text-center">
        <p className="text-[18px] text-ink">This product isn&apos;t sold any more.</p>
        <Link href={`/${store.slug}/products`} className="mt-3 inline-block font-semibold text-sage-deep hover:underline">See all products</Link>
      </div>
    );
  }
  return (
    <div className="mx-auto grid tu-container gap-8 py-8 md:grid-cols-2 md:py-12">
      <div>
        <div className="aspect-[4/5] overflow-hidden rounded-[24px] border border-line bg-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={relayedImageUrl(p.images[photo] ?? p.images[0], 900)} alt={p.name} className="h-full w-full object-contain p-4" />
        </div>
        {p.images.length > 1 && (
          <div className="mt-3 flex gap-2 overflow-x-auto">
            {p.images.map((img, i) => (
              <button
                key={img}
                type="button"
                onClick={() => setPhoto(i)}
                aria-label={`Photo ${i + 1}`}
                className={`h-20 w-16 shrink-0 overflow-hidden rounded-xl border-2 bg-white ${i === photo ? "border-sage" : "border-line"}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={relayedImageUrl(img, 240)} alt="" className="h-full w-full object-contain" />
              </button>
            ))}
          </div>
        )}
      </div>
      <div>
        {p.category && <p className="text-[13px] font-semibold uppercase tracking-[0.12em] text-sage-deep">{p.category}</p>}
        <h1 className="mt-1 font-display text-[clamp(26px,4vw,38px)] leading-tight text-ink">{p.name}</h1>
        <p className="mt-3 text-[26px] font-bold text-ink">{formatPrice(p.price_cents, p.currency)}</p>
        {p.delivers_to_you === false && <p className="mt-1 text-[14px] text-[#a4553f]">This store doesn&apos;t deliver to your country.</p>}
        <div className="mt-5 flex items-center gap-3">
          <span className="text-[15px] font-semibold text-ink">Quantity</span>
          <div className="flex items-center rounded-full border border-line-strong">
            <button type="button" aria-label="One less" onClick={() => setQty((n) => Math.max(1, n - 1))} className="h-10 w-10 text-[20px]">−</button>
            <span className="w-8 text-center text-[16px] font-semibold">{qty}</span>
            <button type="button" aria-label="One more" onClick={() => setQty((n) => Math.min(20, n + 1))} className="h-10 w-10 text-[20px]">+</button>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:max-w-sm">
          <Button
            size="md"
            onClick={() => {
              cart.add(p.id, qty);
              setAdded(true);
            }}
          >
            {added ? "Added to cart" : "Add to cart"}
          </Button>
          <Button
            size="md"
            variant="outline"
            onClick={() => {
              cart.add(p.id, qty);
              router.push(`/${store.slug}/cart`);
            }}
          >
            Buy now
          </Button>
          <Button size="md" variant={tryOn.has(p.id) ? "primary" : "outline"} onClick={() => tryOn.toggle(p.id)}>
            {tryOn.has(p.id) ? "Picked to try on" : "Try it on your photo"}
          </Button>
          {store.whatsapp && (
            <a
              href={waLink(store.whatsapp, `Hi ${store.name}, I'm interested in: ${p.name} (${formatPrice(p.price_cents, p.currency)})`)}
              target="_blank"
              rel="noopener"
              style={{ backgroundColor: WHATSAPP_GREEN }}
              className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full px-5 text-[15px] font-semibold text-white"
            >
              <WhatsAppIcon size={18} /> Ask about it on WhatsApp
            </a>
          )}
        </div>
        {p.description && <p className="mt-6 whitespace-pre-line text-[15.5px] leading-relaxed text-ink-soft">{p.description}</p>}
      </div>
    </div>
  );
}

export function StoreCart({ store }: { store: PublicStore }) {
  const cart = useCart(store.slug);
  const lines = cart.lines
    .map((l) => ({ ...l, product: store.products.find((p) => p.id === l.id) }))
    .filter((l): l is { id: string; qty: number; product: StoreProduct } => !!l.product);
  const currency = lines[0]?.product.currency ?? "usd";
  const total = lines.reduce((sum, l) => sum + l.product.price_cents * l.qty, 0);
  const [form, setForm] = useState({ name: "", phone: "", email: "", address: "", city: "", note: "" });
  const place = useMutation({
    mutationFn: () =>
      storesApi.placeOrder(store.slug, {
        items: lines.map((l) => ({ product_id: l.id, qty: l.qty })),
        name: form.name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim() || undefined,
        address: form.address.trim(),
        city: form.city.trim() || undefined,
        note: form.note.trim() || undefined,
      }),
    onSuccess: () => cart.clear(),
  });
  const field =
    "mt-1.5 h-12 w-full rounded-xl border border-line-strong bg-paper px-3.5 text-[16px] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25";
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (place.isSuccess) {
    const o = place.data;
    return (
      <div className="mx-auto max-w-xl tu-container py-14 text-center">
        <p className="font-display text-[32px] text-ink">Thank you! Your order is placed</p>
        <p className="mt-2 text-[17px] text-ink-soft">
          Order number <b>{o.number}</b> · {formatPrice(o.total_cents, o.currency)}
        </p>
        <p className="mt-3 text-[15.5px] text-muted">
          {store.name} has your order and will contact you to confirm delivery and payment.
          {o.whatsapp_url ? " To be served faster, send it to them on WhatsApp too:" : ""}
        </p>
        {o.whatsapp_url && (
          <a
            href={o.whatsapp_url}
            target="_blank"
            rel="noopener"
            style={{ backgroundColor: WHATSAPP_GREEN }}
            className="mt-5 inline-flex min-h-[52px] items-center gap-2 rounded-full px-6 text-[16.5px] font-semibold text-white"
          >
            <WhatsAppIcon size={22} /> Send my order on WhatsApp
          </a>
        )}
        <div className="mt-6">
          <Link href={`/${store.slug}`} className="font-semibold text-sage-deep hover:underline">Continue shopping</Link>
        </div>
      </div>
    );
  }

  if (lines.length === 0) {
    return (
      <div className="mx-auto tu-container py-20 text-center">
        <p className="font-display text-[28px] text-ink">Your cart is empty</p>
        <Button href={`/${store.slug}/products`} size="md" className="mt-5">
          Shop products
        </Button>
      </div>
    );
  }

  const ready = form.name.trim().length >= 2 && form.phone.replace(/\D/g, "").length >= 7 && form.address.trim().length >= 5;
  return (
    <div className="mx-auto grid tu-container gap-8 py-8 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:py-12">
      <section>
        <h1 className="font-display text-[32px] text-ink">Your cart</h1>
        <ul className="mt-4 space-y-3">
          {lines.map((l) => (
            <li key={l.id} className="flex gap-3 rounded-[18px] border border-line bg-surface p-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={relayedImageUrl(l.product.images[0], 240)} alt="" className="h-24 w-20 shrink-0 rounded-xl bg-white object-contain" />
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-[15px] text-ink">{l.product.name}</p>
                <p className="mt-1 font-bold text-ink">{formatPrice(l.product.price_cents * l.qty, l.product.currency)}</p>
                <div className="mt-2 flex items-center gap-3">
                  <div className="flex items-center rounded-full border border-line-strong">
                    <button type="button" aria-label="One less" onClick={() => cart.setQty(l.id, l.qty - 1)} className="h-9 w-9 text-[18px]">−</button>
                    <span className="w-7 text-center font-semibold">{l.qty}</span>
                    <button type="button" aria-label="One more" onClick={() => cart.setQty(l.id, l.qty + 1)} className="h-9 w-9 text-[18px]">+</button>
                  </div>
                  <button type="button" onClick={() => cart.remove(l.id)} className="text-[14px] text-muted hover:text-[#a4553f]">
                    Remove
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-right text-[20px] font-bold text-ink">Total: {formatPrice(total, currency)}</p>
      </section>

      <form
        className="h-fit rounded-[22px] border border-line bg-surface p-5"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (ready) place.mutate();
        }}
      >
        <h2 className="font-display text-[22px] text-ink">Delivery details</h2>
        <label className="mt-4 block text-[14.5px] font-medium text-ink">Your name<input required value={form.name} onChange={set("name")} className={field} /></label>
        <label className="mt-3 block text-[14.5px] font-medium text-ink">
          Phone / WhatsApp<input required inputMode="tel" value={form.phone} onChange={set("phone")} placeholder="0300 1234567" className={field} />
        </label>
        <label className="mt-3 block text-[14.5px] font-medium text-ink">
          Email (optional, for your receipt)<input type="email" value={form.email} onChange={set("email")} className={field} />
        </label>
        <label className="mt-3 block text-[14.5px] font-medium text-ink">
          Address
          <textarea required rows={2} value={form.address} onChange={set("address")} className={`${field} h-auto py-2.5`} />
        </label>
        <label className="mt-3 block text-[14.5px] font-medium text-ink">City<input value={form.city} onChange={set("city")} className={field} /></label>
        <label className="mt-3 block text-[14.5px] font-medium text-ink">
          Note (optional)<input value={form.note} onChange={set("note")} placeholder="Size, colour, best time to call…" className={field} />
        </label>
        <p className="mt-3 text-[13.5px] text-muted">
          {store.name} confirms your order with you and you pay them as agreed (for example cash on delivery).
        </p>
        {place.isError && (
          <p role="alert" className="mt-2 text-[14px] text-[#a4553f]">
            {place.error instanceof ApiError ? place.error.detail : "Couldn't place the order. Please try again."}
          </p>
        )}
        <Button type="submit" size="md" className="mt-4 w-full" disabled={!ready || place.isPending}>
          {place.isPending ? "Placing your order…" : `Place order · ${formatPrice(total, currency)}`}
        </Button>
      </form>
    </div>
  );
}
