import { SiteChrome } from "@/components/layout/SiteChrome";
import { LooksGrid } from "@/components/looks/LooksGrid";
import type { ReadyLook } from "@/lib/api/endpoints";
import { Hero } from "@/components/marketing/Hero";
import { TrustedBand } from "@/components/marketing/TrustedBand";
import { Section, SectionHead } from "@/components/marketing/primitives";
import { ShowcaseRow } from "@/components/marketing/ShowcaseLooks";
import { Features } from "@/components/marketing/Features";
import { Marketplaces } from "@/components/marketing/Marketplaces";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { FinalCTA } from "@/components/marketing/FinalCTA";
import { FindLookPromo } from "@/components/marketing/FindLookPromo";
import { PhoneHome } from "@/components/app/PhoneHome";
import { HomeFaq } from "@/components/marketing/HomeFaq";
import { JsonLd } from "@/components/seo/JsonLd";
import { serverFetch } from "@/lib/api/server";
import { SITE, SITE_DEFINITION, pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "TryOnU: AI Virtual Try-On. See Clothes on You Before You Buy",
  description:
    "Try real clothes, shoes and accessories on your own photo with AI, then buy from the original store. Whole outfits, an AI stylist, local shops first.",
  path: "/",
});

type Pack = { price_cents: number; currency: string };

// `value` isn't part of React's <meta> typing (the standard attribute is
// `content`), so the props are spread from here.
const IMPACT_SITE_VERIFICATION = {
  name: "impact-site-verification",
  value: "bb9a2fff-6d9d-440c-b556-a52fa0297c6e",
};

export default async function HomePage() {
  const packs = (await serverFetch<Pack[]>("/api/v1/credits/packages", { revalidateSeconds: 3600 })) ?? [];
  const readyLooks = (await serverFetch<ReadyLook[]>("/api/v1/looks", { revalidateSeconds: 300 })) ?? [];
  const prices = packs.map((p) => p.price_cents / 100);
  const app = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: "TryOnU",
    url: SITE,
    description: SITE_DEFINITION,
    applicationCategory: "LifestyleApplication",
    applicationSubCategory: "Virtual try-on and fashion shopping",
    operatingSystem: "Any (web browser)",
    browserRequirements: "Requires a modern web browser",
    featureList: [
      "Virtual try-on of clothes, shoes and accessories on your own photo",
      "Whole outfits of up to five pieces in one picture",
      "AI Stylist that finds real products from a plain-language request",
      "Shop now links to the original store for every product",
      "Local shops that deliver to you shown first",
      "Share a look; friends can try it on themselves",
      "Find the look: search the shops with a photo or screenshot of an outfit",
    ],
    publisher: { "@id": `${SITE}/#organization` },
    ...(prices.length
      ? {
          offers: {
            "@type": "AggregateOffer",
            priceCurrency: (packs[0]?.currency ?? "usd").toUpperCase(),
            lowPrice: Math.min(...prices).toFixed(2),
            highPrice: Math.max(...prices).toFixed(2),
            offerCount: prices.length,
            url: `${SITE}/pricing`,
          },
        }
      : {}),
  };
  return (
    <SiteChrome>
      <JsonLd data={app} />
      {/* Impact.com site verification. Written as a literal element rather
          than through Next's metadata API because Impact's tag carries the
          token in `value`, and the metadata API only ever emits `content`.
          React hoists it into <head>. */}
      <meta {...IMPACT_SITE_VERIFICATION} />
      <PhoneHome />
      <Hero />
      <TrustedBand />

      <Section id="studio">
        <SectionHead
          kicker="Try-on studio"
          title={
            <>
              See it <em>on you</em>
            </>
          }
          sub="Women, men and kids: the same person before and after. Drag the line to compare."
        />
        <ShowcaseRow />
      </Section>

      {readyLooks.length > 0 && (
        <Section id="ready-looks" className="bg-paper-2/50">
          <SectionHead
            kicker="Winter collection"
            title={
              <>
                Ready looks, <em>try them on you</em>
              </>
            }
            sub="Complete outfits from real shops. Pick one, see it on your own photo, then buy each piece."
          />
          <LooksGrid initial={readyLooks} limit={3} />
          <div className="mt-6 text-center">
            <a href="/looks" className="font-display text-[17px] text-sage-deep hover:underline">
              See all ready looks →
            </a>
          </div>
        </Section>
      )}

      <FindLookPromo />
      <Features />
      <Marketplaces />
      <HowItWorks />
      <HomeFaq />
      <FinalCTA />
    </SiteChrome>
  );
}
