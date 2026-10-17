import type { Metadata } from "next";
import { PostDetail } from "@/components/community/PostDetail";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Community look", robots: PRIVATE_PAGE };

export default async function CommunityPostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <SiteChrome>
      <PostDetail id={id} />
    </SiteChrome>
  );
}
