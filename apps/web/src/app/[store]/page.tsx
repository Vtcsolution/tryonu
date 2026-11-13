import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { JsonLd, breadcrumbJsonLd } from "@/components/seo/JsonLd";
import { StoreHome } from "@/components/storefront/StorePages";
import { resolveMediaUrl } from "@/lib/api/client";
import { pageMeta } from "@/lib/seo";
import { loadStore, storeJsonLd } from "@/lib/storefront";

type Props = { params: Promise<{ store: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const store = await loadStore((await params).store);
  if (!store) return { title: "Store", robots: { index: false, follow: true } };
  return pageMeta({
    title: `${store.name}: Shop & Try On`,
    description: (store.description || `Shop ${store.name} and try any product on your own photo before you buy.`).slice(0, 155),
    path: `/${store.slug}`,
    keywords: [store.name, `${store.name} online`],
    image: store.logo_url ? resolveMediaUrl(store.logo_url) : undefined,
  });
}

export default async function Page({ params }: Props) {
  const store = await loadStore((await params).store);
  if (!store) notFound();
  return (
    <>
      <JsonLd data={[storeJsonLd(store), breadcrumbJsonLd([{ name: "TryOnU", path: "/" }, { name: store.name, path: `/${store.slug}` }])]} />
      <StoreHome store={store} />
    </>
  );
}
