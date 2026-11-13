import { serverFetch } from "@/lib/api/server";
import type { PublicStore, StoreProduct } from "@/lib/api/types";
import { resolveMediaUrl } from "@/lib/api/client";
import { SITE } from "@/lib/seo";

/** A store's own page data (tryonu.app/<store>), fetched on the server; null when no such open store. */
export function loadStore(slug: string) {
  // the website's own pages never get here (they're matched first), and a
  // store slug is lowercase letters, digits and dashes
  if (!/^[a-z0-9][a-z0-9-]{0,139}$/.test(slug)) return Promise.resolve(null);
  return serverFetch<PublicStore>(`/api/v1/stores/public/${encodeURIComponent(slug)}`, { revalidateSeconds: 120 });
}

/** schema.org Product for one store product, with its offer on the store's own page. */
export function productJsonLd(store: PublicStore, p: StoreProduct) {
  const url = `${SITE}/${store.slug}/products/${p.id}`;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: p.name,
    url,
    image: p.images.map((i) => resolveMediaUrl(i)),
    description: p.description || undefined,
    category: p.category || undefined,
    color: p.color || undefined,
    brand: { "@type": "Brand", name: store.name },
    offers: {
      "@type": "Offer",
      url,
      price: (p.price_cents / 100).toFixed(2),
      priceCurrency: p.currency.toUpperCase(),
      availability: "https://schema.org/InStock",
      seller: { "@type": "Organization", name: store.name },
    },
  };
}

/** schema.org OnlineStore for a store's home page, with its products listed. */
export function storeJsonLd(store: PublicStore) {
  return {
    "@context": "https://schema.org",
    "@type": "OnlineStore",
    name: store.name,
    url: `${SITE}/${store.slug}`,
    logo: store.logo_url ? resolveMediaUrl(store.logo_url) : undefined,
    description: store.description || undefined,
    sameAs: store.website_url ? [store.website_url] : undefined,
    hasOfferCatalog: {
      "@type": "OfferCatalog",
      name: `${store.name} products`,
      itemListElement: store.products.slice(0, 50).map((p) => ({
        "@type": "Offer",
        url: `${SITE}/${store.slug}/products/${p.id}`,
        price: (p.price_cents / 100).toFixed(2),
        priceCurrency: p.currency.toUpperCase(),
        itemOffered: { "@type": "Product", name: p.name, image: p.images[0] ? resolveMediaUrl(p.images[0]) : undefined },
      })),
    },
  };
}
