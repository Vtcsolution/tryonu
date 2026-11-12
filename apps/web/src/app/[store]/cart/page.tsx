import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StoreCart } from "@/components/storefront/StorePages";
import { PRIVATE_PAGE } from "@/lib/seo";
import { loadStore } from "@/lib/storefront";

type Props = { params: Promise<{ store: string }> };

export const metadata: Metadata = { title: "Cart", robots: PRIVATE_PAGE };

export default async function Page({ params }: Props) {
  const store = await loadStore((await params).store);
  if (!store) notFound();
  return <StoreCart store={store} />;
}
