import Link from "next/link";
import type { CSSProperties } from "react";
import type { ReadyLook } from "@/lib/api/endpoints";

const pct = (v: number, of: number) => `${(v / of) * 100}%`;
// a size on the 1080-wide picture, as a share of the frame's width (scales with it)
const cqw = (px: number, w: number) => `${(px / w) * 100}cqw`;

/** A Ready look as its outfit picture: the try-on picture filling the frame
 * and each product's card ("1. Sunglasses", photo, price) at the sides with a
 * line to where it's worn, every card a link to the shop. Drawn from the
 * layout the server used for the picture file, so both look the same.
 * href: the whole picture (outside the cards) opens this page. */
export function LookCanvas({ look, href, priority = false }: { look: ReadyLook; href?: string; priority?: boolean }) {
  const L = look.layout;
  const alt = `${look.title}: ${look.items.map((it) => it.name).join(", ")}`;
  if (!L) {
    // looks made before the layout was kept: the picture file itself
    return (
      <div className="relative aspect-[4/5] overflow-hidden bg-paper-2">
        {href && <Link href={href} className="absolute inset-0 z-[1]" aria-label={look.title} />}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={look.card_url} alt={alt} fetchPriority={priority ? "high" : "auto"} loading={priority ? "eager" : "lazy"} decoding="async" className="h-full w-full object-cover" />
      </div>
    );
  }
  const [ix, iy, iw, ih] = L.image;
  const box = (b: number[]): CSSProperties => ({ left: pct(b[0], L.w), top: pct(b[1], L.h), width: pct(b[2], L.w), height: pct(b[3], L.h) });

  return (
    <div className="@container relative aspect-[4/5] overflow-hidden bg-paper-2">
      {/* a soft copy behind, then the try-on picture where the server put it */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={look.image_url} alt="" aria-hidden="true" className="absolute inset-0 h-full w-full scale-110 object-cover blur-2xl" />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={look.image_url}
        alt={alt}
        fetchPriority={priority ? "high" : "auto"}
        loading={priority ? "eager" : "lazy"}
        decoding="async"
        style={box([ix, iy, iw, ih])}
        className="absolute max-w-none"
      />
      {href && <Link href={href} className="absolute inset-0 z-[1]" aria-label={look.title} />}

      <svg viewBox={`0 0 ${L.w} ${L.h}`} className="pointer-events-none absolute inset-0 z-[2] h-full w-full" aria-hidden="true">
        {L.tiles.map((t) => {
          const [[sx, sy], [ax, ay]] = t.line;
          return (
            <g key={t.n}>
              <line x1={sx} y1={sy + 1} x2={ax} y2={ay + 1} stroke="rgba(0,0,0,.3)" strokeWidth={5} />
              <line x1={sx} y1={sy} x2={ax} y2={ay} stroke="white" strokeWidth={3} />
              <circle cx={ax} cy={ay} r={9} fill="white" stroke="rgba(40,40,40,.6)" strokeWidth={2} />
              <circle cx={ax} cy={ay} r={3} fill="#57634f" />
            </g>
          );
        })}
      </svg>

      {L.tiles.map((t) => {
        const it = look.items[t.item];
        if (!it) return null;
        const [x, y, w, h] = t.box;
        const [, , , picH] = t.img;
        const labelH = h - picH - 8;
        const text = `${t.n}. ${t.label}`;
        // as big as the card's label area allows, never wider than the card
        const size = Math.min(Math.max(16, labelH * 0.36), (w - 16) / (text.length * 0.56));
        return (
          <a
            key={t.n}
            href={it.buy_url}
            target="_blank"
            rel="noopener sponsored"
            title={`${it.name}: ${t.price}${it.shop ? ` at ${it.shop}` : ""}`}
            style={{ ...box([x, y, w, h]), borderRadius: cqw(20, L.w) }}
            className="absolute z-[3] flex flex-col overflow-hidden border-2 border-[#e2d6ce] bg-[#fcf9f6] shadow-[0_6px_16px_rgba(0,0,0,.25)] transition-transform hover:scale-[1.03] focus-visible:outline-2 focus-visible:outline-sage"
          >
            <span className="block shrink-0 bg-white" style={{ margin: cqw(8, L.w), height: pct(picH, h), borderRadius: cqw(14, L.w) }}>
              {(it.thumb_url || it.image_url) && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={it.thumb_url || it.image_url || ""}
                  alt=""
                  loading={priority ? "eager" : "lazy"}
                  decoding="async"
                  referrerPolicy="no-referrer"
                  className="block h-full w-full object-contain"
                />
              )}
            </span>
            <span className="flex flex-1 flex-col items-center justify-center text-center leading-tight">
              <span className="whitespace-nowrap font-display font-bold text-[#1c1b17]" style={{ fontSize: cqw(size, L.w) }}>
                {text}
              </span>
              <span className="mt-[0.4cqw] whitespace-nowrap font-bold text-[#57634f]" style={{ fontSize: cqw(size * 0.8, L.w) }}>
                {t.price}
              </span>
            </span>
          </a>
        );
      })}
    </div>
  );
}
