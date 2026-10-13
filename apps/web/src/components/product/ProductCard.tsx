"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { formatPrice } from "@/components/try/shop";

export type CardAction = {
  label: ReactNode;
  onClick?: () => void;
  href?: string;
  /** opens in a new tab (shop links) */
  external?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
};

/**
 * The one product card used everywhere products are listed: after a prompt,
 * in search results, on the AI Stylist page and on company store pages.
 *
 * Built to be easy for everyone, 10 to 90 years old: the whole product on a
 * white background (never cropped), large readable text, a clear price, the
 * shop it comes from, and at most two big buttons with plain words.
 */
export function ProductCard({
  image,
  name,
  priceCents,
  currency,
  shop,
  label,
  badge,
  note,
  selected = false,
  busy = false,
  primary,
  secondary,
  compact = false,
}: {
  image?: string | null;
  name: string;
  priceCents: number;
  currency: string;
  shop?: string | null;
  /** what the piece is: "Earrings", "Outfit" */
  label?: string | null;
  /** a short status in the top-right corner: "Swapped in", "Selected" */
  badge?: string | null;
  /** one quiet line under the price */
  note?: string | null;
  selected?: boolean;
  busy?: boolean;
  primary?: CardAction;
  secondary?: CardAction;
  /** a narrower card for side-scrolling rows */
  compact?: boolean;
}) {
  return (
    <article
      className={`group flex h-full flex-col overflow-hidden rounded-[20px] border bg-surface transition-[box-shadow,transform,border-color] duration-200 ${
        selected
          ? "border-sage ring-2 ring-sage/40"
          : "border-line hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[0_10px_28px_rgba(20,20,16,0.10)]"
      }`}
    >
      <div className="relative aspect-[4/5] bg-white">
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={image}
            alt={name}
            loading="lazy"
            className="h-full w-full object-contain p-3 transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="grid h-full place-items-center text-[13px] text-faint">No photo</div>
        )}
        {label && (
          <span className="absolute left-2.5 top-2.5 rounded-full bg-black/75 px-2.5 py-1 text-[12px] font-semibold text-white">
            {label}
          </span>
        )}
        {badge && (
          <span className="absolute right-2.5 top-2.5 rounded-full bg-sage px-2.5 py-1 text-[12px] font-semibold text-white">
            {badge}
          </span>
        )}
        {busy && (
          <span className="absolute inset-0 grid place-items-center bg-surface/60" aria-label="Working">
            <span className="h-7 w-7 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
          </span>
        )}
      </div>

      <div className={`flex flex-1 flex-col ${compact ? "p-3" : "p-3.5"}`}>
        {shop && (
          <p className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-sage" aria-hidden="true" />
            <span className="truncate">{shop}</span>
          </p>
        )}
        <p className={`mt-1 line-clamp-2 leading-snug text-ink ${compact ? "text-[13px]" : "text-[14px]"}`} title={name}>
          {name}
        </p>
        <p className={`mt-2 font-bold text-ink ${compact ? "text-[16px]" : "text-[18px]"}`}>{formatPrice(priceCents, currency)}</p>
        {note && <p className="mt-1 text-[12px] text-muted">{note}</p>}

        {(primary || secondary) && (
          <div className="mt-auto grid gap-2 pt-3.5">
            {primary && <ActionButton action={primary} kind="primary" />}
            {secondary && <ActionButton action={secondary} kind="secondary" />}
          </div>
        )}
      </div>
    </article>
  );
}

function ActionButton({ action, kind }: { action: CardAction; kind: "primary" | "secondary" }) {
  const cls = `tu-press inline-flex min-h-[44px] w-full items-center justify-center gap-1.5 rounded-full px-4 text-[14px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
    kind === "primary"
      ? "bg-sage text-white hover:bg-sage-deep"
      : "border border-line-strong bg-surface text-ink hover:border-ink/50"
  }`;
  if (action.href && !action.disabled) {
    if (action.external) {
      return (
        <a href={action.href} target="_blank" rel="noopener sponsored" className={cls} aria-label={action.ariaLabel}>
          {action.label}
        </a>
      );
    }
    return (
      <Link href={action.href} className={cls} aria-label={action.ariaLabel}>
        {action.label}
      </Link>
    );
  }
  return (
    <button type="button" onClick={action.onClick} disabled={action.disabled} className={cls} aria-label={action.ariaLabel}>
      {action.label}
    </button>
  );
}
