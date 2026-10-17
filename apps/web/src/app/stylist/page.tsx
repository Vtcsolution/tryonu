import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { StylistChat } from "@/components/stylist/StylistChat";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "AI Stylist",
  description: "Tell the AI stylist what you need — it recommends real products from the catalog, never invented ones.",
  robots: PRIVATE_PAGE,
};

export default function StylistPage() {
  return (
    <SiteChrome>
      <StylistChat />
    </SiteChrome>
  );
}
