"use client";

import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/components/try/shop";
import { useQuery } from "@tanstack/react-query";
import { relayedImageUrl } from "@/lib/api/client";
import { showcase, type ShowcaseItem } from "@/lib/api/endpoints";

/**
 * Interactive before/after wipe: one model, before and after a real TryOnU
 * try-on of real shop products (public/showcase). The models are AI-generated in
 * a studio, not real customers, so the caption says so. Each pair is framed on
 * the same face and feet, so the wipe lines up. Winter looks for women, men and
 * children; the products under the picture come live from the shops
 * (GET /api/v1/showcase/look?look=...), and these saved details only show until
 * that answers.
 */
export type LookId = "women" | "men" | "kids";

const LOOKS: Record<LookId, { before: string; after: string; beforeAlt: string; afterAlt: string; placeholder: ShowcaseItem[] }> = {
  women: {
    before: "/showcase/studio-before.jpg",
    after: "/showcase/studio-after.jpg",
    beforeAlt: "Before: a model in a white T-shirt, light-blue jeans and white sneakers",
    afterAlt: "After a TryOnU try-on: the same model in a camel double-breasted coat, a black midi dress, black ankle boots and a leather bag",
    placeholder: [
      { name: "Camel double-breasted long coat", shop: "eBay", price_cents: 5769, currency: "usd", image_url: "https://i.ebayimg.com/images/g/za0AAeSwp0RpSKM2/s-l1600.jpg", buy_url: "" },
      { name: "Naturalizer black leather ankle boots", shop: "eBay", price_cents: 4999, currency: "usd", image_url: "https://i.ebayimg.com/images/g/AOQAAeSw3JVq2UD~/s-l1600.jpg", buy_url: "" },
      { name: "Chloé leather bracelet bag", shop: "Giglio", price_cents: 146250, currency: "gbp", image_url: "https://img.giglio.com/images/prodZoom/I31201.032_1.jpg", buy_url: "" },
    ],
  },
  men: {
    before: "/showcase/men-before.jpg",
    after: "/showcase/men-after.jpg",
    beforeAlt: "Before: a male model in a white T-shirt, grey trousers and white sneakers",
    afterAlt: "After a TryOnU try-on: the same model in a charcoal wool overcoat, a cream cable-knit sweater, a navy wool scarf and brown Chelsea boots",
    placeholder: [
      { name: "Charcoal wool double-breasted overcoat", shop: "eBay", price_cents: 12000, currency: "usd", image_url: "https://i.ebayimg.com/images/g/C1UAAeSwSiVq3lsJ/s-l1600.jpg", buy_url: "" },
      { name: "Polo Ralph Lauren cable-knit sweater", shop: "eBay", price_cents: 9600, currency: "usd", image_url: "https://i.ebayimg.com/images/g/9sAAAeSwV71qwA-P/s-l1600.jpg", buy_url: "" },
      { name: "Maison Margiela ribbed wool scarf", shop: "Giglio", price_cents: 22500, currency: "gbp", image_url: "https://img.giglio.com/images/prodZoom/I24007.045_1.jpg", buy_url: "" },
      { name: "Brown leather Chelsea boots", shop: "eBay", price_cents: 17546, currency: "usd", image_url: "https://i.ebayimg.com/images/g/oI0AAeSwRfNq0Le8/s-l1600.jpg", buy_url: "" },
    ],
  },
  kids: {
    before: "/showcase/kids-before.jpg",
    after: "/showcase/kids-after.jpg",
    beforeAlt: "Before: a child in a white long-sleeve T-shirt, jeans and white sneakers",
    afterAlt: "After a TryOnU try-on: the same child in a red hooded puffer jacket, a white knit beanie and black snow boots",
    placeholder: [
      { name: "Red hooded puffer jacket", shop: "eBay", price_cents: 1099, currency: "usd", image_url: "https://i.ebayimg.com/images/g/vu4AAeSwrGFq0QQI/s-l1600.jpg", buy_url: "" },
      { name: "Carhartt kids knit beanie", shop: "eBay", price_cents: 2999, currency: "usd", image_url: "https://i.ebayimg.com/images/g/9h0AAeSwtbBq32GM/s-l1600.jpg", buy_url: "" },
      { name: "Waterproof winter snow boots", shop: "eBay", price_cents: 2499, currency: "usd", image_url: "https://i.ebayimg.com/images/g/dOgAAOSwnB5nGbff/s-l1600.jpg", buy_url: "" },
    ],
  },
};

function LookThumb({ src, alt }: { src: string; alt: string }) {
  const [url, setUrl] = useState(relayedImageUrl(src, 240));
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt={alt} loading="lazy" onError={() => url !== src && setUrl(src)} className="h-full w-full object-contain p-1.5" />
  );
}

export function CompareSlider({ look: lookId = "women" }: { look?: LookId }) {
  const L = LOOKS[lookId];
  const [pos, setPos] = useState(50);
  const live = useQuery({
    queryKey: ["showcase", "look", lookId],
    queryFn: () => showcase.look(lookId),
    placeholderData: L.placeholder,
    staleTime: 30 * 60_000,
  });
  const items = live.data ?? L.placeholder;
  // the more of the "after" picture is showing, the more the products stand out
  const afterShown = pos <= 55;
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
    <div className="relative mx-auto w-full max-w-[560px]">
      {/* a portrait frame, like the photos: the whole person shows on every screen */}
      <div
        ref={frame}
        className="relative mx-auto aspect-[2/3] w-full overflow-hidden rounded-[28px] border border-line bg-paper-2 shadow-lift"
      >
        {/* result (base) */}
        <Image
          src={L.after}
          alt={L.afterAlt}
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
              src={L.before}
              alt={L.beforeAlt}
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
      {/* right under the picture: every product in the "after" look, with its price and shop link */}
      <div className="mt-4">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">In this look</p>
        <ul className="mt-2 grid grid-cols-1 gap-2.5 min-[420px]:grid-cols-2">
          {items.map((p) => (
            <li key={p.name}>
              <a
                href={p.buy_url || "/try"}
                target={p.buy_url ? "_blank" : undefined}
                rel={p.buy_url ? "noopener sponsored" : undefined}
                className={`group flex items-center gap-3 rounded-[18px] border bg-surface p-2 pr-3 transition-[border-color,box-shadow] duration-300 hover:border-sage ${
                  afterShown ? "border-sage/60 shadow-[0_0_0_3px_rgba(108,122,107,0.12)]" : "border-line"
                }`}
              >
                <span className="h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-white">
                  <LookThumb src={p.image_url} alt={p.name} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14.5px] font-semibold text-ink">{p.name}</span>
                  <span className="block text-[14px] font-semibold text-sage-deep">
                    {formatPrice(p.price_cents, p.currency)} <span aria-hidden="true">→</span>
                  </span>
                  <span className="block truncate text-[12.5px] text-muted">{p.shop}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-center text-[13.5px] text-muted">
          A real TryOnU try-on of real shop products, shown on an AI-generated model. Prices come live from the shops.
        </p>
        <FirstOutfitOffer className="mt-4 w-full" />
        <Button href="/try" size="lg" variant="outline" className="mt-3 w-full">
          Try it on yourself <span aria-hidden="true">→</span>
        </Button>
      </div>
    </div>
  );
}
