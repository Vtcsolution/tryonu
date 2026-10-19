import type { Metadata } from "next";
import { ChallengesList } from "@/components/community/ChallengePage";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Style challenges", robots: PRIVATE_PAGE };

export default function CommunityChallengesPage() {
  return (
    <SiteChrome>
      <ChallengesList />
    </SiteChrome>
  );
}
