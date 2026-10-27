import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { TeamPanel } from "@/components/looks/TeamPanel";

export const metadata: Metadata = { title: "Team panel", robots: { index: false, follow: false } };

export default function TeamPage() {
  return (
    <SiteChrome>
      <TeamPanel />
    </SiteChrome>
  );
}
