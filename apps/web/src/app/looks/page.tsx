import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { LooksGrid } from "@/components/looks/LooksGrid";
import type { ReadyLook } from "@/lib/api/endpoints";
import { serverFetch } from "@/lib/api/server";
import { pageMeta } from "@/lib/seo";

export const revalidate = 300;

export const metadata = pageMeta({
  title: "Ready Looks: Winter Outfits to Try On You",
  description:
    "Complete winter outfits for women, men and kids, put together from real shops. See each look on your own photo before you buy, then shop every piece.",
  path: "/looks",
  keywords: ["winter outfits", "winter outfit ideas", "outfit ideas for women", "outfit ideas for men", "kids winter outfits", "shop the look"],
});

/** tryonu.app/looks: complete outfits the TryOnU team tried on a model, every
 * piece from a real shop, each ready to try on yourself. */
export default async function LooksPage() {
  const looks = (await serverFetch<ReadyLook[]>("/api/v1/looks", { revalidateSeconds: 300 })) ?? [];
  return (
    <SiteChrome>
      <section className="tu-container py-10 md:py-14">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Winter collection</p>
        <h1 className="mt-1 max-w-3xl font-display text-[clamp(32px,4.8vw,54px)] leading-[1.05] text-ink">
          Ready looks, <em>to try on you</em>
        </h1>
        <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-ink-soft">
          Complete outfits put together from real shops. Pick a look, see it on your own photo, then buy each piece from its shop.
        </p>
        <FirstOutfitOffer variant="banner" className="mt-6 max-w-3xl" />
        <div className="mt-8">
          <LooksGrid initial={looks} />
        </div>
      </section>
    </SiteChrome>
  );
}
