import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StoreProducts } from "@/components/storefront/StorePages";
import { pageMeta } from "@/lib/seo";
import { loadStore } from "@/lib/storefront";

type Props = { params: Promise<{ store: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const store = await loadStore((await params).store);
  if (!store) return { title: "Store", robots: { index: false, follow: true } };
  return pageMeta({
    title: `All products: ${store.name}`,
    description: `Every product from ${store.name}. Try any of them on your own photo before you buy.`,
    path: `/${store.slug}/products`,
    keywords: [store.name],
  });
}

export default async function Page({ params }: Props) {
  const store = await loadStore((await params).store);
  if (!store) notFound();
  return <StoreProducts store={store} />;
}
