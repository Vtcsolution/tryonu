import type { Metadata } from "next";
import { ChallengePage } from "@/components/community/ChallengePage";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Style challenge", robots: PRIVATE_PAGE };

export default async function CommunityChallengePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <SiteChrome>
      <ChallengePage id={id} />
    </SiteChrome>
  );
}
