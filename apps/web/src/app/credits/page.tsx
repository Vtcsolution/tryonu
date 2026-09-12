import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { BuyCreditsPanel } from "@/components/credits/BuyCreditsPanel";

export const metadata: Metadata = {
  title: "Buy credits",
  description: "Top up your TryOnU credits for virtual try-ons.",
};

export default function CreditsPage() {
  return (
    <SiteChrome>
      <BuyCreditsPanel />
    </SiteChrome>
  );
}
