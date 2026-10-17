import type { Metadata } from "next";
import { ProfileView } from "@/components/community/ProfileView";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Community profile", robots: PRIVATE_PAGE };

export default async function ProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  return (
    <SiteChrome>
      <ProfileView handle={decodeURIComponent(handle)} />
    </SiteChrome>
  );
}
