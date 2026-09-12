import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { WardrobePage } from "@/components/wardrobe/WardrobePage";

export const metadata: Metadata = {
  title: "My wardrobe",
  description: "Catalog what you already own, then ask the AI stylist to build around it.",
};

export default function Wardrobe() {
  return (
    <SiteChrome>
      <WardrobePage />
    </SiteChrome>
  );
}
