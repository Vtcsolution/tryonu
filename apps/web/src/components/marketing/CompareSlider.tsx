"use client";

import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/components/try/shop";
import { API_BASE_URL, relayedImageUrl } from "@/lib/api/client";

/**
 * Interactive before/after wipe: one model, before and after a real TryOnU
 * try-on of real shop products (public/showcase). The model is AI-generated in
 * a studio, not a real customer, so the caption says so. Both pictures are
 * framed on the same head and feet, so the wipe lines up.
 */
const BEFORE = { src: "/showcase/studio-before.jpg", alt: "Before: a model in a white T-shirt, light-blue jeans and white sneakers" };
const AFTER = {
  src: "/showcase/studio-after.jpg",
  alt: "After a TryOnU try-on: the same model in a camel double-breasted coat, a black midi dress, black ankle boots and a leather bag",
};
// the real shop products in the "after" picture. Each link finds the product
// live again and opens its shop (affiliate link); a listing that has ended
// opens the try-on page instead.
const LOOK: { name: string; shop: string; price: number; currency: string; image: string; r: string; id: string; q: string }[] = [
  {
    name: "Max Mara jersey midi dress",
    shop: "Giglio",
    price: 24000,
    currency: "gbp",
    image: "https://img.giglio.com/images/prodZoom/I35070.002_1.jpg",
    r: "rakuten",
    id: "13639623",
    q: "women black midi dress",
  },
  {
    name: "Camel double-breasted long coat",
    shop: "eBay",
    price: 5769,
    currency: "usd",
    image: "https://i.ebayimg.com/images/g/za0AAeSwp0RpSKM2/s-l1600.jpg",
    r: "ebay",
    id: "v1|397232866979|665629854938",
    q: "women camel wool long coat",
  },
  {
    name: "Naturalizer black leather ankle boots",
    shop: "eBay",
    price: 4999,
    currency: "usd",
    image: "https://i.ebayimg.com/images/g/AOQAAeSw3JVq2UD~/s-l1600.jpg",
    r: "ebay",
    id: "v1|278445526745|2561029494610",
    q: "women black leather ankle boots",
  },
  {
    name: "Chloé leather bracelet bag",
    shop: "Giglio",
    price: 146250,
    currency: "gbp",
    image: "https://img.giglio.com/images/prodZoom/I31201.032_1.jpg",
    r: "rakuten",
    id: "13617007",
    q: "women tan leather handbag",
  },
];

const shopLink = (p: (typeof LOOK)[number]) =>
  `${API_BASE_URL}/api/v1/affiliate/live?${new URLSearchParams({ r: p.r, id: p.id, q: p.q, source: "product_card" })}`;

function LookThumb({ src, alt }: { src: string; alt: string }) {
  const [url, setUrl] = useState(relayedImageUrl(src, 240));
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt={alt} loading="lazy" onError={() => url !== src && setUrl(src)} className="h-full w-full object-contain p-1.5" />
  );
}

export function CompareSlider() {
  const [pos, setPos] = useState(50);
  const id = useId();
  // the "original" half is drawn at the frame's full width, then clipped
  const frame = useRef<HTMLDivElement>(null);
  const [frameWidth, setFrameWidth] = useState<number | null>(null);
  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setFrameWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="relative mx-auto grid max-w-[1080px] items-center gap-8 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)] lg:gap-12">
      {/* a portrait frame, like the photos: the whole person shows on every screen */}
      <div
        ref={frame}
        className="relative mx-auto aspect-[2/3] w-full max-w-[460px] overflow-hidden rounded-[28px] border border-line bg-paper-2 shadow-lift lg:max-w-[560px]"
      >
        {/* result (base) */}
        <Image
          src={AFTER.src}
          alt={AFTER.alt}
          fill
          className="object-cover"
          sizes="(max-width: 500px) 100vw, 560px"
        />

        {/* original (clipped overlay) */}
        <div
          className="absolute inset-y-0 left-0 overflow-hidden border-r-2 border-white"
          style={{ width: `${pos}%` }}
        >
          <div
            className="absolute inset-y-0 left-0"
            style={{ width: frameWidth ? `${frameWidth}px` : "100%" }}
          >
            <Image
              src={BEFORE.src}
              alt={BEFORE.alt}
              fill
              className="object-cover"
              sizes="(max-width: 500px) 100vw, 560px"
            />
          </div>
        </div>

        {/* scrim keeps the labels legible over any photo */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 z-[5] h-20 bg-gradient-to-b from-black/25 to-transparent"
        />

        <span className="absolute left-4 top-4 z-[15] rounded-full bg-white/90 px-3 py-1.5 text-[12px] font-semibold text-[#1c1b17] backdrop-blur">
          Before
        </span>
        <span className="absolute right-4 top-4 z-[15] rounded-full bg-sage px-3 py-1.5 text-[12px] font-semibold text-white">
          After try-on
        </span>

        {/* handle */}
        <div
          className="pointer-events-none absolute inset-y-0 z-10 w-0.5 bg-white/90"
          style={{ left: `${pos}%` }}
        >
          <div className="absolute left-1/2 top-1/2 grid h-12 w-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-[#1c1b17] shadow-lift">
            <span aria-hidden="true">↔</span>
          </div>
        </div>

        <input
          id={id}
          type="range"
          min={0}
          max={100}
          value={pos}
          onChange={(e) => setPos(Number(e.target.value))}
          aria-label="Reveal original vs try-on result"
          className="absolute inset-0 z-20 h-full w-full cursor-ew-resize opacity-0"
        />

      </div>
      {/* beside the picture on computers, under it on phones: the products in the look */}
      <div className="mx-auto w-full max-w-[460px] lg:max-w-none">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Shop this look</p>
        <p className="mt-1 font-display text-[26px] leading-tight text-ink">4 real products, one try-on</p>
        <ul className="tu-stagger mt-4 space-y-2.5">
          {LOOK.map((p) => (
            <li key={p.id}>
              <a
                href={shopLink(p)}
                target="_blank"
                rel="noopener sponsored"
                className="group flex items-center gap-3 rounded-[18px] border border-line bg-surface p-2.5 pr-4 transition-colors hover:border-sage"
              >
                <span className="h-[72px] w-[60px] shrink-0 overflow-hidden rounded-xl bg-white">
                  <LookThumb src={p.image} alt={p.name} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15.5px] font-semibold text-ink">{p.name}</span>
                  <span className="block text-[14px] text-muted">
                    {p.shop} · <b className="text-ink">{formatPrice(p.price, p.currency)}</b>
                  </span>
                </span>
                <span className="shrink-0 text-[14.5px] font-semibold text-sage-deep group-hover:translate-x-0.5" aria-hidden="true">
                  Shop →
                </span>
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[13.5px] text-muted">
          A real TryOnU try-on of real shop products, shown on an AI-generated model. Prices are the shops&apos; and can change.
        </p>
        <Button href="/try" size="lg" className="mt-5 w-full">
          Try it on yourself <span aria-hidden="true">→</span>
        </Button>
      </div>
    </div>
  );
}
