import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { OutfitsPage } from "@/components/outfits/OutfitsPage";

export const metadata: Metadata = {
  title: "Outfit builder",
  description: "Combine real products into a complete outfit — see a live compatibility score as you build.",
};

export default function Outfits() {
  return (
    <SiteChrome>
      <OutfitsPage />
    </SiteChrome>
  );
}
