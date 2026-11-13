import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { JsonLd, breadcrumbJsonLd } from "@/components/seo/JsonLd";
import { StoreProductPage } from "@/components/storefront/StorePages";
import { resolveMediaUrl } from "@/lib/api/client";
import { pageMeta } from "@/lib/seo";
import { loadStore, productJsonLd } from "@/lib/storefront";

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
  const p = store.products.find((x) => x.id === id);
  return (
    <>
      {p && (
        <JsonLd
          data={[
            productJsonLd(store, p),
            breadcrumbJsonLd([
              { name: store.name, path: `/${store.slug}` },
              { name: "Products", path: `/${store.slug}/products` },
              { name: p.name, path: `/${store.slug}/products/${p.id}` },
            ]),
          ]}
        />
      )}
      <StoreProductPage store={store} productId={id} />
    </>
  );
}
