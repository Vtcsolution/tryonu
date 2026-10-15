"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { ZoomableImage } from "@/components/try/ZoomableImage";
import { stores as storesApi } from "@/lib/api/endpoints";
import type { Store, StoreTryOnPicture } from "@/lib/api/types";
import { countryFlag, countryName } from "@/lib/countries";

/**
 * A store's page for shoppers' try-ons of its products: how many free
 * try-ons it has left, which products shoppers try on, and the pictures
 * shoppers agreed to share, each opening full screen.
 */
export function ShopperTryOns({ store, onBuyMore }: { store: Store; onBuyMore: () => void }) {
  const data = useQuery({ queryKey: ["business", "tryons"], queryFn: storesApi.tryons, refetchOnWindowFocus: true });
  const [open, setOpen] = useState<number | null>(null);

  if (data.isLoading) return <div className="mx-auto my-16 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  if (data.isError || !data.data) {
    return <p className="rounded-[16px] border border-line p-6 text-center text-[14px] text-muted">Couldn&apos;t load your try-ons. Please refresh.</p>;
  }
  const d = data.data;
  const low = d.credits_left <= Math.max(3, Math.round(d.plan_credits * 0.1));

  return (
    <div className="space-y-6">
      {/* how it works, in plain words */}
      <section className="rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6">
        <h2 className="font-display text-[22px] text-ink">How shopper try-ons work</h2>
        <ol className="mt-3 space-y-2 text-[14.5px] leading-relaxed text-ink-soft">
          <li><b className="text-ink">1.</b> A shopper finds your product and presses <b>Try it on</b>.</li>
          <li><b className="text-ink">2.</b> The try-on is <b>free for them</b>: it uses <b>1 of your try-on credits</b>. They see your product on their own photo.</li>
          <li><b className="text-ink">3.</b> If they agree, their try-on picture appears below, so you can see your product on real people.</li>
          <li><b className="text-ink">4.</b> If a try-on fails, your credit comes back automatically.</li>
        </ol>
        <p className="mt-3 text-[13px] text-muted">
          Shoppers can also pay with their own credits and keep their picture private. Then you only see that your product was tried on.
        </p>
      </section>

      {/* the numbers that matter */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile
          label="Try-on credits left"
          value={d.credits_left.toLocaleString()}
          note={d.plan_credits ? `Your plan gives ${d.plan_credits} each period` : "Comes with a plan"}
          tone={low ? "warn" : undefined}
        />
        <Tile label="Used in the last 30 days" value={d.used_30d.toLocaleString()} note="Paid with your credits" />
        <Tile label="All try-ons of your products" value={d.tryons_total.toLocaleString()} note="Free and paid by shoppers" />
        <Tile label="Pictures shared with you" value={d.pictures.length.toLocaleString()} note={`${d.private_tryons} kept private`} />
      </div>
      {low && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-[#c9a13b]/40 bg-[#c9a13b]/10 px-4 py-3">
          <p className="text-[14px] text-ink">
            {d.credits_left === 0
              ? "You have no try-on credits left. Shoppers can still try your products, but they pay for it themselves."
              : `Only ${d.credits_left} try-on credits left.`}
          </p>
          <button
            type="button"
            onClick={onBuyMore}
            className="tu-press min-h-[40px] rounded-full bg-sage px-4 text-[14px] font-semibold text-white hover:bg-sage-deep"
          >
            Get more with a plan →
          </button>
        </div>
      )}

      {/* the pictures */}
      <section className="rounded-[24px] border border-line bg-surface p-6">
        <h2 className="font-display text-[20px] text-ink">Shoppers wearing your products</h2>
        <p className="mt-1 text-[13.5px] text-muted">Tap a picture to see it full screen. Newest first.</p>
        {d.pictures.length === 0 ? (
          <p className="mt-4 rounded-[16px] border border-dashed border-line p-8 text-center text-[14px] text-muted">
            No pictures yet. They appear here when shoppers try on your products and share their picture.
          </p>
        ) : (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {d.pictures.map((p, i) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setOpen(i)}
                className="group overflow-hidden rounded-[18px] border border-line bg-surface text-left transition-shadow hover:shadow-[0_10px_28px_rgba(20,20,16,0.12)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage"
                aria-label={`Open the try-on of ${p.product_name}`}
              >
                <div className="relative aspect-[3/4] bg-paper-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={p.image_url} alt="" loading="lazy" className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]" />
                  <span className="absolute right-2 top-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-semibold text-white">⤢ Full screen</span>
                </div>
                <div className="p-3">
                  <p className="line-clamp-2 text-[13px] leading-snug text-ink">{p.product_name}</p>
                  <p className="mt-1 text-[12px] text-muted">
                    {new Date(p.created_at).toLocaleDateString()}
                    {p.shopper_country ? ` · ${countryFlag(p.shopper_country)} ${countryName(p.shopper_country)}` : ""}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* per product */}
      <section className="rounded-[24px] border border-line bg-surface p-6">
        <h2 className="font-display text-[20px] text-ink">Try-ons per product</h2>
        {d.products.length === 0 ? (
          <p className="mt-3 text-[14px] text-muted">None of your products has been tried on yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-[14px]">
              <thead>
                <tr className="border-b border-line text-[12px] uppercase tracking-[0.08em] text-faint">
                  <th className="py-2 pr-3 font-medium">Product</th>
                  <th className="py-2 pr-3 font-medium">Tried on</th>
                  <th className="py-2 pr-3 font-medium">Paid with your credits</th>
                  <th className="py-2 font-medium">Pictures shared</th>
                </tr>
              </thead>
              <tbody>
                {d.products.map((p) => (
                  <tr key={p.store_product_id ?? p.name} className="border-b border-line last:border-0">
                    <td className="py-2.5 pr-3 text-ink">{p.name}</td>
                    <td className="py-2.5 pr-3 font-semibold text-ink">{p.tryons}</td>
                    <td className="py-2.5 pr-3 text-ink-soft">{p.paid_by_store}</td>
                    <td className="py-2.5 text-ink-soft">{p.shared}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {open !== null && d.pictures[open] && (
        <Viewer pictures={d.pictures} index={open} onIndex={setOpen} onClose={() => setOpen(null)} storeName={store.name} />
      )}
    </div>
  );
}

function Tile({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: "warn" }) {
  return (
    <div className={`rounded-[18px] border p-4 ${tone === "warn" ? "border-[#c9a13b]/50 bg-[#c9a13b]/10" : "border-line bg-surface"}`}>
      <p className="text-[12px] uppercase tracking-[0.08em] text-faint">{label}</p>
      <p className="mt-1 font-display text-[28px] text-ink">{value}</p>
      {note && <p className="mt-0.5 text-[12.5px] text-muted">{note}</p>}
    </div>
  );
}

/** One try-on picture full screen: zoom and drag it, step through the rest. */
function Viewer({
  pictures,
  index,
  onIndex,
  onClose,
  storeName,
}: {
  pictures: StoreTryOnPicture[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  storeName: string;
}) {
  const p = pictures[index];
  const prev = useCallback(() => onIndex((index - 1 + pictures.length) % pictures.length), [index, pictures.length, onIndex]);
  const next = useCallback(() => onIndex((index + 1) % pictures.length), [index, pictures.length, onIndex]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    };
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = overflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose, prev, next]);

  const button = "tu-press grid h-11 w-11 place-items-center rounded-full bg-white/15 text-[20px] text-white hover:bg-white/25";
  return (
    <div role="dialog" aria-modal="true" aria-label={`Try-on of ${p.product_name}`} className="fixed inset-0 z-[60] flex flex-col bg-black/95">
      <div className="flex items-center gap-3 px-4 py-3 text-white">
        <p className="min-w-0 flex-1 truncate text-[14px]">
          <b>{p.product_name}</b>
          <span className="text-white/60">
            {" "}· {new Date(p.created_at).toLocaleString()}
            {p.shopper_country ? ` · ${countryFlag(p.shopper_country)} ${countryName(p.shopper_country)}` : ""}
            {p.paid_by_store ? ` · paid by ${storeName}` : ""}
          </span>
        </p>
        <span className="text-[13px] text-white/60">
          {index + 1} / {pictures.length}
        </span>
        <button type="button" onClick={onClose} className={button} aria-label="Close">
          ✕
        </button>
      </div>
      <div className="flex min-h-0 flex-1 items-stretch gap-3 px-3 pb-3">
        {pictures.length > 1 && (
          <button type="button" onClick={prev} className={`${button} self-center`} aria-label="Previous picture">
            ‹
          </button>
        )}
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-[16px] bg-black">
          <ZoomableImage key={p.id} src={p.image_url} alt={`A shopper wearing ${p.product_name}`} />
        </div>
        {pictures.length > 1 && (
          <button type="button" onClick={next} className={`${button} self-center`} aria-label="Next picture">
            ›
          </button>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3 px-4 pb-4 text-[13px] text-white/70">
        {p.product_image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={p.product_image} alt="" className="h-12 w-12 rounded-lg bg-white object-contain p-1" />
        )}
        <span>Zoom with the + and − buttons, the mouse wheel or two fingers, then drag. ← → for the next picture.</span>
        {p.product_url && (
          <a href={p.product_url} target="_blank" rel="noopener noreferrer" className="font-medium text-white underline">
            Your product page ↗
          </a>
        )}
      </div>
    </div>
  );
}
