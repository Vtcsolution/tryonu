import type { Metadata } from "next";
import { CommunityFeed } from "@/components/community/CommunityFeed";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Community",
  description: "Looks TryOnU members tried on: like, comment, follow, and try any look on yourself.",
  robots: PRIVATE_PAGE,
};

export default function CommunityPage() {
  return (
    <SiteChrome>
      <CommunityFeed />
    </SiteChrome>
  );
}
