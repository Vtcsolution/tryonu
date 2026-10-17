import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { ForYouFeed } from "@/components/feed/ForYouFeed";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "For you",
  description: "Fashion picked for your style, live from real stores.",
  robots: PRIVATE_PAGE,
};

export default function ForYouPage() {
  return (
    <SiteChrome>
      <ForYouFeed />
    </SiteChrome>
  );
}
