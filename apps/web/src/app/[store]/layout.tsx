import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { StoreShell } from "@/components/storefront/StoreShell";
import { loadStore } from "@/lib/storefront";

// tryonu.app/<store>: a store's own website, with only its products
export default async function StoreLayout({ children, params }: { children: ReactNode; params: Promise<{ store: string }> }) {
  const { store: slug } = await params;
  const store = await loadStore(slug);
  if (!store) notFound();
  return <StoreShell store={store}>{children}</StoreShell>;
}
