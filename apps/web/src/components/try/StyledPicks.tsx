"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ProductCard } from "@/components/product/ProductCard";
import { affiliateGoUrl, resolveMediaUrl, thumbnailUrl } from "@/lib/api/client";
import { liveSearch } from "@/lib/api/endpoints";
import type { LiveProduct, Product } from "@/lib/api/types";
import { FEATURED, RECOMMENDED, formatPrice, fromTryOnUStore, shopName } from "./shop";

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
  [/\b(sunglasses|eyeglasses|glasses)\b/i, "Glasses"],
  [/\b(khussa|jutti|heels|sandals?|shoes|sneakers|flats|boots|loafers|mojari)\b/i, "Shoes"],
  [/\b(dupatta|shawl|stole|scarf)\b/i, "Dupatta"],
];
const SLOT_LABELS: Record<string, string> = {
  dress: "Outfit",
  top: "Top",
  bottom: "Bottom",
  outerwear: "Jacket",
  shoes: "Shoes",
  watch: "Watch",
  bag: "Bag",
  accessory: "Accessory",
};
const GARMENT_SLOTS = new Set(["dress", "top", "bottom", "outerwear"]);

/** What the piece is, for the label on its card. */
export function pieceLabel(name: string, slot?: string | null): string {
  if (slot && GARMENT_SLOTS.has(slot)) return SLOT_LABELS[slot];
  return PIECE_LABELS.find(([re]) => re.test(name))?.[1] ?? (slot ? SLOT_LABELS[slot] ?? "Item" : "Item");
}

type Sort = "best" | "low" | "high";

// columns follow the number of pieces, so a look fills its row
const GRID: Record<number, string> = {
  1: "max-w-[340px] grid-cols-1",
  2: "max-w-[720px] grid-cols-2",
  3: "grid-cols-2 sm:grid-cols-3",
  4: "grid-cols-2 sm:grid-cols-4",
  5: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5",
};

/** The stylist's picks after a prompt: one card per piece, and for the piece
 *  being changed, its other real options in one panel. */
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
  const anyOptions = items.some((i) => (alternatives[i.product.id] ?? []).length > 0);

  return (
    <section className="mt-5 animate-[tu-in-scale_0.35s_ease] overflow-hidden rounded-[28px] border border-line bg-surface shadow-[0_2px_10px_rgba(20,20,16,0.06)]">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-5 py-5 sm:px-6">
        <div className="min-w-0">
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Your look</p>
          <h3 className="mt-1 font-display text-[26px] leading-tight text-ink">
            {items.length === 1 ? "1 item" : `${items.length} items`}
            {total !== null && <span className="text-ink-soft"> · {formatPrice(total, items[0].product.currency)}</span>}
          </h3>
          {summary && <p className="mt-2 max-w-3xl text-[15.5px] leading-relaxed text-ink-soft">{summary}</p>}
          {anyOptions && (
            <p className="mt-3 inline-flex items-center gap-2 rounded-full bg-sage-tint/60 px-3 py-1.5 text-[14.5px] text-ink">
              Not happy with an item? Tap <b>Change</b> to see other options.
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {onUndo && (
            <button
              type="button"
              onClick={onUndo}
              className="min-h-[40px] rounded-full border border-sage/50 px-4 text-[15px] font-medium text-sage-deep hover:bg-sage-tint/50"
            >
              ↺ Undo
            </button>
          )}
          <button
            type="button"
            onClick={onClear}
            className="min-h-[40px] rounded-full border border-line px-4 text-[15px] text-muted hover:border-line-strong hover:text-ink"
          >
            Start again
          </button>
        </div>
      </header>

      <div className={`grid gap-4 p-5 sm:p-6 ${GRID[Math.min(items.length, 5)]}`}>
        {items.map((item) => {
          const count = (alternatives[item.product.id] ?? []).length;
          const active = item.key === openKey;
          return (
            <ProductCard
              key={item.key}
              image={resolveMediaUrl(item.product.images[0]?.url)}
              name={item.product.name}
              priceCents={item.product.price_cents}
              currency={item.product.currency}
              shop={shopName(item.product.merchant_name, item.product.retailer?.name)}
              label={pieceLabel(item.product.name, item.slot)}
              badge={item.highlight ? "New pick" : fromTryOnUStore(item.product.retailer?.slug) ? RECOMMENDED : null}
              note={item.rendered ? null : "Shown next to your photo"}
              selected={active}
              primary={{
                label: count === 0 ? "No other options" : active ? "Close options" : `Change (${count})`,
                onClick: () => setOpenKey(active ? null : item.key),
                disabled: count === 0,
                attention: !active && count > 0,
              }}
              secondary={{
                label: "View in shop ↗",
                href: affiliateGoUrl(item.product.id, "stylist"),
                external: true,
                ariaLabel: `View ${item.product.name} in the shop`,
              }}
            />
          );
        })}
      </div>

      {open && openOptions.length > 0 && (
        <ChangePanel
          label={pieceLabel(open.product.name, open.slot)}
          options={openOptions}
          sort={sort}
          onSort={setSort}
          onClose={() => setOpenKey(null)}
          key={open.key}
          onUse={(alt) => onUse(alt, open.product.id)}
          onBuy={onBuy}
          busyId={busyId}
        />
      )}
    </section>
  );
}

function ChangePanel({
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
  // the shopper's own search for this piece: any product or brand
  const [text, setText] = useState("");
  const [searched, setSearched] = useState("");
  const found = useQuery({
    queryKey: ["search", "live", searched, 24],
    queryFn: () => liveSearch.search(searched, 24),
    enabled: searched.length > 1,
  });
  const searching = searched.length > 1;
  const shown = searching ? found.data ?? [] : options;
  const sorted = useMemo(() => {
    if (sort === "best") return shown;
    return [...shown].sort((a, b) => (sort === "low" ? a.price_cents - b.price_cents : b.price_cents - a.price_cents));
  }, [shown, sort]);
  const busy = busyId !== undefined;

  return (
    <div className="border-t border-line bg-paper-2/50 px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-[20px] text-ink">
            {searching ? <>Results for &ldquo;{searched}&rdquo;</> : <>Choose a different {label.toLowerCase()}</>}
          </p>
          <p className="text-[14.5px] text-muted">
            {searching && found.isFetching ? "Searching real shops…" : `${shown.length} options`} · tap <b>Choose this</b> to put it in your
            look
            {searching && (
              <>
                {" · "}
                <button
                  type="button"
                  onClick={() => {
                    setSearched("");
                    setText("");
                  }}
                  className="font-semibold text-sage-deep hover:underline"
                >
                  Back to the {options.length} options
                </button>
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Sort options" className="flex rounded-full border border-line bg-surface p-1">
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
                aria-pressed={sort === value}
                onClick={() => onSort(value)}
                className={`min-h-[36px] rounded-full px-3.5 text-[14px] font-medium transition-colors ${
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
            className="min-h-[40px] rounded-full border border-line bg-surface px-4 text-[15px] text-ink hover:border-line-strong"
          >
            Close
          </button>
        </div>
      </div>

      {/* search for this piece by name or brand; it pulses until it's used */}
      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          // nothing typed yet: put the cursor in the box instead
          if (text.trim().length < 2) (e.currentTarget.elements.namedItem("q") as HTMLInputElement | null)?.focus();
          else setSearched(text.trim());
        }}
      >
        <input
          name="q"
          type="search"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (!e.target.value.trim()) setSearched("");
          }}
          placeholder={`Search any ${label.toLowerCase()} or brand, e.g. Gucci, Khaadi, gold`}
          aria-label={`Search any ${label.toLowerCase()} or brand`}
          className={`h-12 min-w-0 flex-1 rounded-full border border-line-strong bg-surface px-4 text-[15.5px] text-ink outline-none placeholder:text-muted focus:border-sage focus:ring-2 focus:ring-sage/25 ${
            text ? "" : "tu-glow"
          }`}
        />
        <button
          type="submit"
          className="tu-press h-12 shrink-0 rounded-full bg-sage px-6 text-[15.5px] font-semibold text-white hover:bg-sage-deep"
        >
          Search
        </button>
      </form>

      {searching && !found.isFetching && shown.length === 0 && (
        <p className="mt-4 rounded-[16px] border border-dashed border-line p-5 text-center text-[15px] text-muted">
          Nothing found. Try other words, or a brand name.
        </p>
      )}

      <div className="mt-4 flex snap-x snap-mandatory gap-4 overflow-x-auto pb-3">
        {searching && found.isFetching &&
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} aria-hidden="true" className="h-[360px] w-[230px] shrink-0 animate-pulse rounded-[20px] bg-paper-2" />
          ))}
        {!(searching && found.isFetching) && sorted.map((alt) => (
          <div key={`${alt.retailer_slug}:${alt.retailer_product_id}`} className="w-[230px] shrink-0 snap-start">
            <ProductCard
              compact
              image={thumbnailUrl(alt.images[0])}
              name={alt.name}
              priceCents={alt.price_cents}
              currency={alt.currency}
              shop={shopName(alt.merchant_name, alt.retailer_name)}
              badge={alt.featured ? FEATURED : fromTryOnUStore(alt.retailer_slug) ? RECOMMENDED : null}
              busy={busyId === alt.retailer_product_id}
              primary={{ label: "Choose this", onClick: () => onUse(alt), disabled: busy }}
              secondary={{ label: "View in shop ↗", onClick: () => onBuy(alt), disabled: busy }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
