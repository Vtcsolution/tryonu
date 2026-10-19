import type { Metadata } from "next";
import { MeHub } from "@/components/app/MeHub";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Me", robots: PRIVATE_PAGE };

export default function MePage() {
  return (
    <SiteChrome>
      <MeHub />
    </SiteChrome>
  );
}
