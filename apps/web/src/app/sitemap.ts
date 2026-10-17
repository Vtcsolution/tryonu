import type { MetadataRoute } from "next";
import { serverFetch } from "@/lib/api/server";
import { SITE } from "@/lib/seo";
import { LANDINGS } from "@/lib/seoContent";

export const revalidate = 3600;

const PAGES: { path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
  { path: "/", priority: 1, changeFrequency: "daily" },
  { path: "/how-it-works", priority: 0.8, changeFrequency: "monthly" },
  { path: "/pricing", priority: 0.8, changeFrequency: "weekly" },
  { path: "/faq", priority: 0.8, changeFrequency: "monthly" },
  { path: "/sell", priority: 0.7, changeFrequency: "monthly" },
  { path: "/earn", priority: 0.6, changeFrequency: "monthly" },
  { path: "/extension", priority: 0.8, changeFrequency: "monthly" },
  { path: "/about", priority: 0.6, changeFrequency: "monthly" },
  { path: "/contact", priority: 0.5, changeFrequency: "yearly" },
  { path: "/sign-up", priority: 0.5, changeFrequency: "yearly" },
  { path: "/business/sign-up", priority: 0.5, changeFrequency: "yearly" },
  { path: "/developers/docs", priority: 0.7, changeFrequency: "monthly" },
  { path: "/developers/sign-up", priority: 0.5, changeFrequency: "yearly" },
  { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
  { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  { path: "/photo-policy", priority: 0.3, changeFrequency: "yearly" },
  { path: "/affiliate-disclosure", priority: 0.3, changeFrequency: "yearly" },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const stores = (await serverFetch<{ slug: string; updated_at: string | null }[]>("/api/v1/stores/public", { revalidateSeconds: 3600 })) ?? [];
  return [
    ...PAGES.map((p) => ({ url: `${SITE}${p.path === "/" ? "" : p.path}`, lastModified: now, changeFrequency: p.changeFrequency, priority: p.priority })),
    ...LANDINGS.map((l) => ({
      url: `${SITE}/${l.slug}`,
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: l.audience === "shopper" ? 0.9 : 0.7,
    })),
    ...stores.map((s) => ({
      url: `${SITE}/stores/${encodeURIComponent(s.slug)}`,
      lastModified: s.updated_at ? new Date(s.updated_at) : now,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
  ];
}
