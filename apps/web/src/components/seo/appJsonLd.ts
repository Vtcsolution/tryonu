import { serverFetch } from "@/lib/api/server";
import { SITE, SITE_DEFINITION } from "@/lib/seo";

type Pack = { name: string; credits: number; price_cents: number; currency: string; new_members_only?: boolean };

/** schema.org WebApplication (a SoftwareApplication) for TryOnU, with the live
 * credit packs as its offers. No ratings: there are no real reviews to show yet. */
export async function appJsonLd() {
  const packs = (await serverFetch<Pack[]>("/api/v1/credits/packages", { revalidateSeconds: 3600 })) ?? [];
  return {
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
    ...(packs.length
      ? {
          offers: [...packs]
            .sort((a, b) => a.price_cents - b.price_cents)
            .map((p) => ({
              "@type": "Offer",
              name: `${p.name}: ${p.credits} credits${p.new_members_only ? " (new members)" : ""}`,
              price: (p.price_cents / 100).toFixed(2),
              priceCurrency: p.currency.toUpperCase(),
              url: `${SITE}/pricing`,
            })),
        }
      : {}),
  };
}
