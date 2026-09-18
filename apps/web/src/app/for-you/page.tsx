import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { ForYouFeed } from "@/components/feed/ForYouFeed";

export const metadata: Metadata = {
  title: "For you",
  description: "Fashion picked for your style, live from real stores.",
};

export default function ForYouPage() {
  return (
    <SiteChrome>
      <ForYouFeed />
    </SiteChrome>
  );
}
