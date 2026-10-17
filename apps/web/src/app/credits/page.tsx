import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { BuyCreditsPanel } from "@/components/credits/BuyCreditsPanel";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Buy credits",
  description: "Top up your TryOnU credits for virtual try-ons.",
  robots: PRIVATE_PAGE,
};

export default function CreditsPage() {
  return (
    <SiteChrome>
      <BuyCreditsPanel />
    </SiteChrome>
  );
}
