import type { Metadata } from "next";
import { ReelsView } from "@/components/community/ReelsView";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Reels", robots: PRIVATE_PAGE };

export default function ReelsPage() {
  return <ReelsView />;
}
