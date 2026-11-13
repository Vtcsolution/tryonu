import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { LooksGrid } from "@/components/looks/LooksGrid";
import { JsonLd } from "@/components/seo/JsonLd";
import type { ReadyLook } from "@/lib/api/endpoints";
import { serverFetch } from "@/lib/api/server";
import { LOOK_COLLECTIONS, MIN_COLLECTION, collectionLooks, lookPath } from "@/lib/looks";
import { SITE, pageMeta } from "@/lib/seo";
import Link from "next/link";

export const revalidate = 300;

export const metadata = pageMeta({
  title: "Shop the Look: Complete Outfits to Try On",
  description:
    "Complete outfits for women and men, put together from real shops. See each look on your own photo before you buy, then shop every piece.",
  path: "/looks",
  keywords: ["shop the look", "complete outfits", "outfit ideas for women", "outfit ideas for men", "try on outfits"],
});

/** tryonu.app/looks: complete outfits the TryOnU team tried on a model, every
 * piece from a real shop, each ready to try on yourself. */
export default async function LooksPage() {
  const looks = (await serverFetch<ReadyLook[]>("/api/v1/looks", { revalidateSeconds: 300 })) ?? [];
  return (
    <SiteChrome>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "ItemList",
          name: "TryOnU ready looks",
          itemListElement: looks.slice(0, 60).map((l, i) => ({
            "@type": "ListItem",
            position: i + 1,
            url: `${SITE}${lookPath(l)}`,
            name: l.title,
            image: l.card_url ?? undefined,
          })),
        }}
      />
      <section className="tu-container py-10 md:py-14">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Winter collection</p>
        <h1 className="mt-1 max-w-3xl font-display text-[clamp(32px,4.8vw,54px)] leading-[1.05] text-ink">
          Ready looks, <em>to try on you</em>
        </h1>
        <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-ink-soft">
          Complete outfits put together from real shops. Pick a look, see it on your own photo, then buy each piece from its shop.
        </p>
        <nav aria-label="Look collections" className="mt-5 flex flex-wrap gap-2">
          {LOOK_COLLECTIONS.filter((c) => collectionLooks(c, looks).length >= MIN_COLLECTION).map((c) => (
            <Link key={c.slug} href={`/looks/${c.slug}`} className="rounded-full border border-line-strong px-4 py-2 text-[15px] font-medium text-ink hover:border-ink/40">
              {c.h1} →
            </Link>
          ))}
        </nav>
        <FirstOutfitOffer variant="banner" className="mt-6 max-w-3xl" />
        <div className="mt-8">
          <LooksGrid initial={looks} />
        </div>
      </section>
    </SiteChrome>
  );
}
