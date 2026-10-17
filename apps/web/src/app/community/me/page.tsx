import type { Metadata } from "next";
import { MyProfileRedirect } from "@/components/community/PostDetail";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "My community profile", robots: PRIVATE_PAGE };

export default function MyCommunityProfilePage() {
  return (
    <SiteChrome>
      <MyProfileRedirect />
    </SiteChrome>
  );
}
