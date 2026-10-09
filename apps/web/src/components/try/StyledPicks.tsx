"use client";

import { useMemo, useState } from "react";
import { affiliateGoUrl, resolveMediaUrl, thumbnailUrl } from "@/lib/api/client";
import type { LiveProduct, Product } from "@/lib/api/types";
import { RetailerTag, formatPrice, shopName } from "./shop";

export type PickItem = {
  key: string;
  product: Product;
  slot?: string | null;
  /** drawn onto the photo (false: shown beside the result with its shop link) */
  rendered: boolean;
  /** just swapped in */
  highlight: boolean;
};

const PIECE_LABELS: [RegExp, string][] = [
  [/\b(nose ?(rings?|pins?|studs?|hoops?)|nath)\b/i, "Nose ring"],
  [/\b(maang ?tikka|tikka)\b/i, "Maang tikka"],
  [/\b(earrings?|jhumkas?|jhumki|ear ?studs?)\b/i, "Earrings"],
  [/\b(necklace|choker|pendant)\b/i, "Necklace"],
  [/\b(watch(es)?|wristwatch)\b/i, "Watch"],
  [/\b(bangles?|bracelets?|kada)\b/i, "Bangles"],
  [/\brings?\b/i, "Ring"],
  [/\b(clutch|handbag|bag|purse|tote)\b/i, "Bag"],
  [/\b(sunglasses|eyeglasses|glasses)\b/i, "Eyewear"],
  [/\b(khussa|jutti|heels|sandals?|shoes|sneakers|flats|boots|loafers|mojari)\b/i, "Shoes"],
  [/\b(dupatta|shawl|stole|scarf)\b/i, "Dupatta"],
];
const SLOT_LABELS: Record<string, string> = {
  dress: "Outfit",
  top: "Top",
  bottom: "Bottom",
  outerwear: "Layer",
  shoes: "Shoes",
  watch: "Watch",
  bag: "Bag",
  accessory: "Accessory",
};
const GARMENT_SLOTS = new Set(["dress", "top", "bottom", "outerwear"]);

/** What the piece is, for the label on its card. */
function pieceLabel(name: string, slot?: string | null): string {
  if (slot && GARMENT_SLOTS.has(slot)) return SLOT_LABELS[slot];
  return PIECE_LABELS.find(([re]) => re.test(name))?.[1] ?? (slot ? SLOT_LABELS[slot] ?? "Item" : "Item");
}

type Sort = "best" | "low" | "high";

// columns follow the number of pieces, so a 4-piece look fills the row
const GRID: Record<number, string> = {
  1: "max-w-[240px] grid-cols-1",
  2: "max-w-[520px] grid-cols-2",
  3: "grid-cols-2 sm:grid-cols-3",
  4: "grid-cols-2 sm:grid-cols-4",
  5: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5",
};

/** The stylist's picks after a prompt: one card per piece and, for the piece
 *  being swapped, its other real options in a single panel. */
export function StyledPicks({
  items,
  alternatives,
  summary,
  onUse,
  onBuy,
  busyId,
  onUndo,
  onClear,
  defaultOpenKey = null,
}: {
  items: PickItem[];
  alternatives: Record<string, LiveProduct[]>;
  summary?: string | null;
  onUse: (alt: LiveProduct, replaceId: string) => void;
  onBuy: (alt: LiveProduct) => void;
  busyId?: string;
  onUndo?: () => void;
  onClear: () => void;
  defaultOpenKey?: string | null;
}) {
  const [openKey, setOpenKey] = useState<string | null>(defaultOpenKey);
  const [sort, setSort] = useState<Sort>("best");

  const currencies = new Set(items.map((i) => i.product.currency.toLowerCase()));
  const total = currencies.size === 1 ? items.reduce((sum, i) => sum + i.product.price_cents, 0) : null;
  const open = items.find((i) => i.key === openKey) ?? null;
  const openOptions = open ? alternatives[open.product.id] ?? [] : [];
  const notDrawn = items.some((i) => !i.rendered);

  return (
    <section className="mt-5 animate-[tu-in-scale_0.35s_ease] overflow-hidden rounded-[24px] border border-line bg-surface shadow-[0_1px_3px_rgba(20,20,16,0.06)]">
      <header className="px-5 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-sage-deep">AI-styled look</p>
            <h3 className="mt-1 font-display text-[22px] leading-tight text-ink">
              {items.length === 1 ? "Your pick" : `${items.length} pieces`}
              {total !== null && (
                <span className="ml-2 align-middle font-sans text-[14px] font-semibold text-ink-soft">
                  · {formatPrice(total, items[0].product.currency)}
                </span>
              )}
            </h3>
          </div>
          <div className="flex items-center gap-3 pt-1">
            {onUndo && (
              <button type="button" onClick={onUndo} className="text-[12.5px] font-medium text-sage-deep hover:underline">
                ↺ Undo swap
              </button>
            )}
            <button type="button" onClick={onClear} className="text-[12.5px] text-faint hover:text-ink hover:underline">
              Clear
            </button>
          </div>
        </div>
        {summary && (
          <p className="mt-3 max-w-3xl border-l-2 border-sage/50 pl-3 text-[13.5px] leading-relaxed text-ink-soft">{summary}</p>
        )}
      </header>

      <div className={`grid gap-3 p-5 ${GRID[Math.min(items.length, 5)]}`}>
        {items.map((item) => (
          <PickCard
            key={item.key}
            item={item}
            optionCount={(alternatives[item.product.id] ?? []).length}
            active={item.key === openKey}
            onSwap={() => setOpenKey((k) => (k === item.key ? null : item.key))}
          />
        ))}
      </div>

      {notDrawn && (
        <p className="-mt-2 px-5 pb-4 text-[12px] text-faint">
          Pieces marked &ldquo;beside photo&rdquo; aren&rsquo;t drawn on you; they&rsquo;re shown next to your result with their own shop link.
        </p>
      )}

      {open && openOptions.length > 0 && (
        <SwapPanel
          label={pieceLabel(open.product.name, open.slot)}
          options={openOptions}
          sort={sort}
          onSort={setSort}
          onClose={() => setOpenKey(null)}
          onUse={(alt) => onUse(alt, open.product.id)}
          onBuy={onBuy}
          busyId={busyId}
        />
      )}
    </section>
  );
}

function PickCard({
  item,
  optionCount,
  active,
  onSwap,
}: {
  item: PickItem;
  optionCount: number;
  active: boolean;
  onSwap: () => void;
}) {
  const { product } = item;
  const image = resolveMediaUrl(product.images[0]?.url);
  const shop = shopName(product.merchant_name, product.retailer?.name);
  return (
    <article
      className={`group flex flex-col overflow-hidden rounded-[18px] border bg-surface transition-shadow ${
        active
          ? "border-sage ring-2 ring-sage/30"
          : item.highlight
            ? "tu-pop border-sage"
            : "border-line hover:border-line-strong hover:shadow-[0_6px_18px_rgba(20,20,16,0.08)]"
      }`}
    >
      <div className="relative aspect-[4/5] bg-white">
        {image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={image}
            alt={product.name}
            className="h-full w-full object-contain p-2 transition-transform duration-300 group-hover:scale-[1.03]"
          />
        )}
        <span className="absolute left-2 top-2 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-semibold text-white backdrop-blur-sm">
          {pieceLabel(product.name, item.slot)}
        </span>
        {item.highlight && (
          <span className="absolute right-2 top-2 rounded-full bg-sage px-2 py-0.5 text-[10px] font-semibold text-white">
            Swapped in
          </span>
        )}
        {!item.rendered && (
          <span className="absolute bottom-2 left-2 rounded-full bg-surface/95 px-2 py-0.5 text-[10px] font-medium text-ink-soft shadow-sm">
            beside photo
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col p-3">
        {shop && <p className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">{shop}</p>}
        <p className="mt-0.5 line-clamp-2 text-[12.5px] leading-snug text-ink" title={product.name}>
          {product.name}
        </p>
        <p className="mt-1.5 text-[14px] font-semibold text-ink">{formatPrice(product.price_cents, product.currency)}</p>
        <div className="mt-auto flex gap-1.5 pt-3">
          <button
            type="button"
            onClick={onSwap}
            disabled={optionCount === 0}
            className={`tu-press h-8 flex-1 rounded-full text-[11.5px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              active ? "bg-sage text-white" : "border border-line-strong text-ink hover:border-ink/40"
            }`}
          >
            {optionCount === 0 ? "No swaps" : active ? "Close" : `Swap · ${optionCount}`}
          </button>
          <a
            href={affiliateGoUrl(product.id, "stylist")}
            target="_blank"
            rel="noopener sponsored"
            title="View in shop"
            aria-label={`View ${product.name} in the shop`}
            className="tu-press grid h-8 w-8 shrink-0 place-items-center rounded-full border border-line-strong text-[13px] text-ink hover:border-ink/40"
          >
            ↗
          </a>
        </div>
      </div>
    </article>
  );
}

function SwapPanel({
  label,
  options,
  sort,
  onSort,
  onClose,
  onUse,
  onBuy,
  busyId,
}: {
  label: string;
  options: LiveProduct[];
  sort: Sort;
  onSort: (s: Sort) => void;
  onClose: () => void;
  onUse: (alt: LiveProduct) => void;
  onBuy: (alt: LiveProduct) => void;
  busyId?: string;
}) {
  const sorted = useMemo(() => {
    if (sort === "best") return options;
    return [...options].sort((a, b) => (sort === "low" ? a.price_cents - b.price_cents : b.price_cents - a.price_cents));
  }, [options, sort]);
  const shops = Array.from(new Set(options.map((o) => shopName(o.merchant_name, o.retailer_name)).filter(Boolean)));
  const busy = busyId !== undefined;

  return (
    <div className="border-t border-line bg-paper-2/60 px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-ink">
          <span className="font-semibold">Swap {label.toLowerCase()}</span>
          <span className="text-muted">
            {" "}
            · {options.length} options{shops.length ? ` from ${shops.slice(0, 3).join(", ")}${shops.length > 3 ? " and more" : ""}` : ""}
          </span>
        </p>
        <div className="flex items-center gap-2">
          <div className="flex rounded-full border border-line bg-surface p-0.5 text-[11.5px]">
            {(
              [
                ["best", "Best match"],
                ["low", "Lowest price"],
                ["high", "Highest price"],
              ] as [Sort, string][]
            ).map(([value, text]) => (
              <button
                key={value}
                type="button"
                onClick={() => onSort(value)}
                className={`rounded-full px-2.5 py-1 transition-colors ${
                  sort === value ? "bg-ink text-surface" : "text-muted hover:text-ink"
                }`}
              >
                {text}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close options"
            className="grid h-7 w-7 place-items-center rounded-full text-[15px] text-muted hover:bg-surface hover:text-ink"
          >
            ×
          </button>
        </div>
      </div>

      <div className="mt-3 flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2">
        {sorted.map((alt) => {
          const thumb = thumbnailUrl(alt.images[0]);
          const working = busyId === alt.retailer_product_id;
          return (
            <div
              key={`${alt.retailer_slug}:${alt.retailer_product_id}`}
              className="flex w-[164px] shrink-0 snap-start flex-col overflow-hidden rounded-[16px] border border-line bg-surface"
            >
              <div className="relative aspect-[4/5] bg-white" title={alt.name}>
                {thumb && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={thumb} alt={alt.name} loading="lazy" className="h-full w-full object-contain p-2" />
                )}
                <RetailerTag name={shopName(alt.merchant_name, alt.retailer_name)} className="absolute left-1.5 top-1.5" />
                {working && (
                  <span className="absolute inset-0 grid place-items-center bg-surface/60">
                    <span className="h-6 w-6 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
                  </span>
                )}
              </div>
              <div className="flex flex-1 flex-col p-2.5">
                <p className="line-clamp-2 text-[11.5px] leading-snug text-ink-soft">{alt.name}</p>
                <p className="mt-1 text-[13px] font-semibold text-ink">{formatPrice(alt.price_cents, alt.currency)}</p>
                <div className="mt-auto flex items-center gap-2 pt-2.5">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onUse(alt)}
                    className="tu-press h-8 flex-1 rounded-full bg-sage text-[11.5px] font-medium text-white hover:bg-sage-deep disabled:opacity-50"
                  >
                    Use this
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onBuy(alt)}
                    className="text-[11.5px] font-medium text-ink-soft underline-offset-2 hover:text-ink hover:underline disabled:opacity-50"
                  >
                    View
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
