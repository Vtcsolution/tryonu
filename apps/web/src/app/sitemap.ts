import type { MetadataRoute } from "next";
import { serverFetch } from "@/lib/api/server";
import { resolveMediaUrl } from "@/lib/api/client";
import { SITE } from "@/lib/seo";
import { LANDINGS } from "@/lib/seoContent";
import { LOOK_COLLECTIONS, MIN_COLLECTION, collectionLooks, lookPath } from "@/lib/looks";
import type { ReadyLook } from "@/lib/api/endpoints";
import { loadStore } from "@/lib/storefront";

export const revalidate = 3600;

const PAGES: { path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
  { path: "/", priority: 1, changeFrequency: "daily" },
  { path: "/looks", priority: 0.9, changeFrequency: "daily" },
  { path: "/how-it-works", priority: 0.8, changeFrequency: "monthly" },
  { path: "/pricing", priority: 0.8, changeFrequency: "weekly" },
  { path: "/faq", priority: 0.8, changeFrequency: "monthly" },
  { path: "/sell", priority: 0.7, changeFrequency: "monthly" },
  { path: "/earn", priority: 0.6, changeFrequency: "monthly" },
  { path: "/extension", priority: 0.8, changeFrequency: "monthly" },
  { path: "/find-look", priority: 0.8, changeFrequency: "monthly" },
  { path: "/app", priority: 0.6, changeFrequency: "yearly" },
  { path: "/about", priority: 0.6, changeFrequency: "monthly" },
  { path: "/contact", priority: 0.5, changeFrequency: "yearly" },
  { path: "/developers", priority: 0.8, changeFrequency: "monthly" },
  { path: "/developers/docs", priority: 0.7, changeFrequency: "monthly" },
  { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
  { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  { path: "/refunds", priority: 0.3, changeFrequency: "yearly" },
  { path: "/photo-policy", priority: 0.3, changeFrequency: "yearly" },
  { path: "/affiliate-disclosure", priority: 0.3, changeFrequency: "yearly" },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const stores = (await serverFetch<{ slug: string; updated_at: string | null }[]>("/api/v1/stores/public", { revalidateSeconds: 3600 })) ?? [];
  const looks = (await serverFetch<ReadyLook[]>("/api/v1/looks?limit=96", { revalidateSeconds: 3600 })) ?? [];
  const storePages = (await Promise.all(stores.slice(0, 200).map((s) => loadStore(s.slug)))).filter((s) => s !== null);
  return [
    ...PAGES.map((p) => ({ url: `${SITE}${p.path === "/" ? "" : p.path}`, changeFrequency: p.changeFrequency, priority: p.priority })),
    ...LANDINGS.map((l) => ({
      url: `${SITE}/${l.slug}`,
      changeFrequency: "monthly" as const,
      priority: l.audience === "shopper" ? 0.9 : 0.7,
    })),
    ...LOOK_COLLECTIONS.filter((c) => collectionLooks(c, looks).length >= MIN_COLLECTION).map((c) => ({
      url: `${SITE}/looks/${c.slug}`,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...looks.map((l) => ({
      url: `${SITE}${lookPath(l)}`,
      ...(l.created_at ? { lastModified: new Date(l.created_at) } : {}),
      changeFrequency: "weekly" as const,
      priority: 0.7,
      images: [l.card_url],
    })),
    ...stores.map((s) => ({
      url: `${SITE}/${encodeURIComponent(s.slug)}`,
      ...(s.updated_at ? { lastModified: new Date(s.updated_at) } : {}),
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...storePages.flatMap((s) => [
      { url: `${SITE}/${s.slug}/products`, changeFrequency: "weekly" as const, priority: 0.5 },
      ...s.products.map((p) => ({
        url: `${SITE}/${s.slug}/products/${p.id}`,
        changeFrequency: "weekly" as const,
        priority: 0.5,
        images: p.images.slice(0, 1).map((i) => resolveMediaUrl(i)),
      })),
    ]),
  ];
}
