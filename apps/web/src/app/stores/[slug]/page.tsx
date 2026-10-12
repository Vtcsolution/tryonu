import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PublicStore } from "@/components/business/PublicStore";

export const metadata: Metadata = {
  title: "Store",
  description: "A store on TryOnU: try its products on your own photo before you buy.",
};

export default async function StorePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <SiteChrome>
      <PublicStore slug={slug} />
    </SiteChrome>
  );
}
