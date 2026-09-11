import { Reveal } from "@/components/ui/Reveal";
import { Button } from "@/components/ui/Button";
import { Section, SectionHead } from "./primitives";
import { affiliateGoUrl, resolveMediaUrl } from "@/lib/api/client";
import { serverFetch } from "@/lib/api/server";
import type { Page, Product } from "@/lib/api/types";
import { PHOTOS } from "@/lib/media";

type CardData = { id: string | null; retailer: string; name: string; price: string; image: string; href: string };

// Static fallback — same three products the live catalog is seeded with
// (see apps/api/app/retailers/sample.py), so this never looks different
// from the API-backed version; it only renders if the API is unreachable.
const FALLBACK: CardData[] = [
  {
    id: null,
    retailer: "Amazon",
    name: "Cream Knit Poncho",
    price: "$32.00",
    image: PHOTOS.productSweater.src,
    href: "https://www.example-retailer.com/cream-knit-poncho",
  },
  {
    id: null,
    retailer: "eBay",
    name: "Red Evening Dress",
    price: "$49.90",
    image: PHOTOS.productDress.src,
    href: "https://www.example-retailer.com/red-evening-dress",
  },
  {
    id: null,
    retailer: "Flipkart",
    name: "Rust Bomber Jacket",
    price: "₹3,499",
    image: PHOTOS.productJacket.src,
    href: "https://www.example-retailer.com/rust-bomber-jacket",
  },
];

export async function Marketplaces() {
  const page = await serverFetch<Page<Product>>("/api/v1/products?limit=3&sort=newest");

  const cards: CardData[] =
    page && page.items.length > 0
      ? page.items.map((p) => ({
          id: p.id,
          retailer: p.retailer.name,
          name: p.name,
          price: `${(p.price_cents / 100).toFixed(2)} ${p.currency.toUpperCase()}`,
          image: resolveMediaUrl(p.images[0]?.url) || PHOTOS.productSweater.src,
          href: affiliateGoUrl(p.id, "product_card"),
        }))
      : FALLBACK;

  return (
    <Section id="marketplaces">
      <SectionHead
        kicker="Real marketplaces"
        title={
          <>
            Same you. <em>More choices.</em>
          </>
        }
        sub="One fitting profile, every store. Try the look, then buy it from the original retailer — TryOnU never sits between you and checkout."
      />

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((p, i) => (
          <Reveal
            key={p.id ?? p.name}
            delay={i * 80}
            className="group tu-hover-card overflow-hidden rounded-[24px] border border-line bg-surface hover:border-line-strong"
          >
            <div className="relative h-[300px] overflow-hidden">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={p.image}
                alt={p.name}
                className="tu-hover-media h-full w-full object-cover object-top"
              />
              <span className="absolute left-3.5 top-3.5 rounded-lg bg-surface/95 px-2.5 py-1.5 text-[12px] font-semibold text-ink">
                {p.retailer}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 p-5">
              <div>
                <h4 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">
                  {p.name}
                </h4>
                <p className="mt-0.5 text-[13px] text-muted">{p.price}</p>
              </div>
              <Button href={p.href} size="sm" variant="outline">
                Shop now <span aria-hidden="true">→</span>
              </Button>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
