import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PublicStore } from "@/components/business/PublicStore";
import { JsonLd, breadcrumbJsonLd } from "@/components/seo/JsonLd";
import { serverFetch } from "@/lib/api/server";
import type { PublicStore as PublicStoreData } from "@/lib/api/types";
import { countryName } from "@/lib/countries";
import { resolveMediaUrl } from "@/lib/api/client";
import { SITE, pageMeta } from "@/lib/seo";

type Props = { params: Promise<{ slug: string }> };

async function load(slug: string) {
  return serverFetch<PublicStoreData>(`/api/v1/stores/public/${encodeURIComponent(slug)}`, { revalidateSeconds: 600 });
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const store = await load(slug);
  if (!store) return { title: "Store", robots: { index: false, follow: true } };
  const where = countryName(store.country);
  const kinds = [...new Set(store.products.map((p) => p.category).filter(Boolean))].slice(0, 4).join(", ");
  const description = (
    store.description ||
    `${store.name} sells ${kinds || "fashion"}${where ? ` in ${where}` : ""}. Try any product on your own photo with AI before you buy.`
  ).slice(0, 155);
  return pageMeta({
    title: `${store.name}: Try On & Shop${where ? ` (${where})` : ""}`,
    description,
    path: `/stores/${store.slug}`,
    keywords: [store.name, `${store.name} online`, ...(where ? [`clothes shop ${where}`] : [])],
    image: store.logo_url ? resolveMediaUrl(store.logo_url) : undefined,
  });
}

export default async function StorePage({ params }: Props) {
  const { slug } = await params;
  const store = await load(slug);
  const structured = store
    ? [
        {
          "@context": "https://schema.org",
          "@type": "Store",
          name: store.name,
          url: `${SITE}/stores/${store.slug}`,
          ...(store.description ? { description: store.description } : {}),
          ...(store.logo_url ? { logo: resolveMediaUrl(store.logo_url), image: resolveMediaUrl(store.logo_url) } : {}),
          ...(store.website_url ? { sameAs: [store.website_url] } : {}),
          address: { "@type": "PostalAddress", addressCountry: store.country },
          makesOffer: store.products.slice(0, 50).map((p) => ({
            "@type": "Offer",
            price: (p.price_cents / 100).toFixed(2),
            priceCurrency: p.currency.toUpperCase(),
            itemOffered: {
              "@type": "Product",
              name: p.name,
              ...(p.description ? { description: p.description.slice(0, 300) } : {}),
              ...(p.images[0] ? { image: resolveMediaUrl(p.images[0]) } : {}),
              ...(p.category ? { category: p.category } : {}),
            },
          })),
        },
        breadcrumbJsonLd([
          { name: "TryOnU", path: "/" },
          { name: store.name, path: `/stores/${store.slug}` },
        ]),
      ]
    : null;
  return (
    <SiteChrome>
      {structured && <JsonLd data={structured} />}
      <PublicStore slug={slug} initial={store} />
    </SiteChrome>
  );
}
