import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { StylistChat } from "@/components/stylist/StylistChat";

export const metadata: Metadata = {
  title: "AI Stylist",
  description: "Tell the AI stylist what you need — it recommends real products from the catalog, never invented ones.",
};

export default function StylistPage() {
  return (
    <SiteChrome>
      <StylistChat />
    </SiteChrome>
  );
}
