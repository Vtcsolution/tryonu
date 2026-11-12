import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StoreProductPage } from "@/components/storefront/StorePages";
import { resolveMediaUrl } from "@/lib/api/client";
import { pageMeta } from "@/lib/seo";
import { loadStore } from "@/lib/storefront";

type Props = { params: Promise<{ store: string; id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { store: slug, id } = await params;
  const store = await loadStore(slug);
  const p = store?.products.find((x) => x.id === id);
  if (!store || !p) return { title: "Product", robots: { index: false, follow: true } };
  return pageMeta({
    title: `${p.name}: ${store.name}`,
    description: (p.description || `${p.name} from ${store.name}. Try it on your own photo before you buy.`).slice(0, 155),
    path: `/${store.slug}/products/${p.id}`,
    keywords: [store.name, p.category ?? ""].filter(Boolean),
    image: p.images[0] ? resolveMediaUrl(p.images[0]) : undefined,
  });
}

export default async function Page({ params }: Props) {
  const { store: slug, id } = await params;
  const store = await loadStore(slug);
  if (!store) notFound();
  return <StoreProductPage store={store} productId={id} />;
}
