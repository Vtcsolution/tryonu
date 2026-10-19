"use client";

import Link from "next/link";
import { Fragment, type ReactNode } from "react";
import { formatPrice } from "@/components/try/shop";
import { relayedImageUrl, resolveMediaUrl } from "@/lib/api/client";
import type { CommunityProduct, LinkPreview } from "@/lib/api/endpoints";

export function timeAgo(iso: string): string {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  if (d < 7) return `${d}d`;
  return new Date(iso).toLocaleDateString();
}

export function Avatar({
  name,
  handle,
  url,
  size = 40,
  className = "",
}: {
  name: string | null;
  handle: string;
  url?: string | null;
  size?: number;
  className?: string;
}) {
  const letter = (name || handle || "?").trim().charAt(0).toUpperCase();
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={resolveMediaUrl(url)}
      alt=""
      width={size}
      height={size}
      className={`shrink-0 rounded-full object-cover ${className}`}
      style={{ width: size, height: size }}
    />
  ) : (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-full bg-sage font-semibold text-white ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {letter}
    </span>
  );
}

// the server keeps only TryOnU links in captions and comments; show them as links
const LINK_RE = /(https?:\/\/[^\s<>"']+|(?:www\.|api\.)?tryonu\.app[^\s<>"']*)/gi;
const TRAILING = /[.,!?;:)\]}'"]+$/;

function linkTarget(raw: string): { href: string; internal: boolean } {
  try {
    const url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
    const own = url.hostname === "tryonu.app" || url.hostname === "www.tryonu.app" || (typeof window !== "undefined" && url.hostname === window.location.hostname);
    return own ? { href: `${url.pathname}${url.search}${url.hash}` || "/", internal: true } : { href: url.toString(), internal: false };
  } catch {
    return { href: raw, internal: false };
  }
}

// @username: a link to that member's profile (no regex look-behind: older iPhones can't read it)
const MENTION_RE = /@[A-Za-z0-9_.]{3,30}/g;

function WithMentions({ text }: { text: string }) {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(MENTION_RE)) {
    const at = m.index ?? 0;
    const before = at > 0 ? text[at - 1] : "";
    if (/[\w@]/.test(before)) continue; // part of an email or a word
    const handle = m[0].slice(1).replace(/\.+$/, "");
    out.push(text.slice(last, at));
    out.push(
      <Link key={at} href={`/u/${handle.toLowerCase()}`} className="font-semibold text-sage-deep hover:underline">
        @{handle}
      </Link>,
    );
    last = at + 1 + handle.length;
  }
  out.push(text.slice(last));
  return <>{out}</>;
}

/** Text with its TryOnU links and @mentions clickable. */
export function RichText({ text, mention }: { text: string; mention?: string | null }) {
  const parts = text.split(LINK_RE);
  return (
    <>
      {mention && <span className="font-semibold text-sage-deep">@{mention} </span>}
      {parts.map((part, i) => {
        if (i % 2 === 0) return <WithMentions key={i} text={part} />;
        const trail = part.match(TRAILING)?.[0] ?? "";
        const raw = trail ? part.slice(0, -trail.length) : part;
        const { href, internal } = linkTarget(raw);
        return (
          <Fragment key={i}>
            {internal ? (
              <Link href={href} className="break-all font-medium text-sage-deep underline underline-offset-2">
                {raw.replace(/^https?:\/\//i, "")}
              </Link>
            ) : (
              <a href={href} target="_blank" rel="noopener sponsored" className="break-all font-medium text-sage-deep underline underline-offset-2">
                {raw.replace(/^https?:\/\//i, "")}
              </a>
            )}
            {trail}
          </Fragment>
        );
      })}
    </>
  );
}

const KIND_LABEL: Record<LinkPreview["kind"], string> = { store: "Store", product: "Product", look: "Look", post: "Post" };

/** Small cards for the TryOnU store, product, look and post links in a text. */
export function LinkCards({ previews }: { previews?: LinkPreview[] }) {
  if (!previews?.length) return null;
  return (
    <div className="mt-2 space-y-2">
      {previews.map((p) => (
        <Link
          key={p.url}
          href={p.url}
          className="flex max-w-[420px] items-center gap-3 rounded-xl border border-line bg-surface p-2 pr-3 transition-colors hover:border-line-strong"
        >
          <span className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-paper-2">
            {p.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={p.kind === "product" ? relayedImageUrl(p.image_url, 200) : resolveMediaUrl(p.image_url)}
                alt=""
                loading="lazy"
                className={`h-full w-full ${p.kind === "product" || p.kind === "store" ? "bg-white object-contain" : "object-cover object-top"}`}
              />
            ) : (
              <span className="text-[12px] font-semibold text-muted">{KIND_LABEL[p.kind]}</span>
            )}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[11.5px] font-semibold uppercase tracking-[0.08em] text-faint">
              TryOnU {KIND_LABEL[p.kind].toLowerCase()}
            </span>
            <span className="block truncate text-[14.5px] font-semibold text-ink">{p.title}</span>
            <span className="block truncate text-[13px] text-muted">
              {p.price_cents ? <b className="font-semibold text-sage-deep">{formatPrice(p.price_cents, p.currency ?? "usd")}</b> : null}
              {p.price_cents && p.subtitle ? " · " : ""}
              {p.subtitle}
            </span>
          </span>
        </Link>
      ))}
    </div>
  );
}

/** A row of a look's products, each one opening the shop. */
export function ProductChips({ products, className = "" }: { products: CommunityProduct[]; className?: string }) {
  if (!products.length) return null;
  return (
    <div className={`flex gap-2 overflow-x-auto pb-1 ${className}`}>
      {products.map((prod) => (
        <a
          key={prod.id}
          href={prod.buy_url}
          target="_blank"
          rel="noopener sponsored"
          className="flex w-[150px] shrink-0 items-center gap-2 rounded-xl border border-line bg-surface p-1.5 hover:border-line-strong"
          title={prod.name}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={relayedImageUrl(prod.image_url, 200)} alt="" loading="lazy" className="h-11 w-11 shrink-0 rounded-lg bg-white object-contain" />
          <span className="min-w-0">
            <span className="block truncate text-[12.5px] text-ink">{prod.name}</span>
            <span className="block text-[12px] font-semibold text-sage-deep">
              {prod.price_cents > 0 ? formatPrice(prod.price_cents, prod.currency) : "Shop"} →
            </span>
          </span>
        </a>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ icons (outline, like LinkedIn)

type IconProps = { size?: number };

export function HeartIcon({ filled = false, size = 19 }: { filled?: boolean; size?: number }) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={filled ? 0 : 1.9} strokeLinejoin="round">
      <path d="M12 20.3s-7.6-4.6-9.3-9.4C1.6 7.6 3.6 4.5 6.9 4.5c2.1 0 3.5 1.2 4.4 2.6h1.4c.9-1.4 2.3-2.6 4.4-2.6 3.3 0 5.3 3.1 4.2 6.4-1.7 4.8-9.3 9.4-9.3 9.4z" />
    </svg>
  );
}

export function ThumbIcon({ filled = false, size = 20 }: { filled?: boolean; size?: number }) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path
        d="M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.6l-2.3 8a2 2 0 0 1-1.9 1.4H7V10l4.6-7.6A2.9 2.9 0 0 1 15 5.9z"
        fill={filled ? "currentColor" : "none"}
      />
      <path d="M7 10H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" fill={filled ? "currentColor" : "none"} />
    </svg>
  );
}

export function CommentIcon({ size = 19 }: IconProps) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
      <path d="M4 5.5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9.5L5 21v-3.5H4a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z" />
    </svg>
  );
}

export function SendIcon({ size = 19 }: IconProps) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.5 2.5 10.8 13.2" />
      <path d="M21.5 2.5 14.7 21.2a.5.5 0 0 1-.9 0l-3-8-8-3a.5.5 0 0 1 0-.9z" />
    </svg>
  );
}

export function BookmarkIcon({ filled = false, size = 19 }: { filled?: boolean; size?: number }) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
      <path d="M6 3.5h12a1 1 0 0 1 1 1V21l-7-4.5L5 21V4.5a1 1 0 0 1 1-1z" />
    </svg>
  );
}

export function PhotoIcon({ size = 19 }: IconProps) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <circle cx="9" cy="9" r="2" />
      <path d="m21 15-4-4L6 21" />
    </svg>
  );
}

export function HangerIcon({ size = 20 }: IconProps) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 7.5a2 2 0 1 1 2-2" />
      <path d="M12 7.5v1.6L3.4 15.2a1.4 1.4 0 0 0 .8 2.5h15.6a1.4 1.4 0 0 0 .8-2.5L12 9.1" />
    </svg>
  );
}
