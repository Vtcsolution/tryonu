import type { Metadata } from "next";
import { PostDetail } from "@/components/community/PostDetail";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";
import { loadSharePreview, shareWords } from "./share";

type Props = { params: Promise<{ id: string }> };

// LinkedIn, WhatsApp, Facebook and X read these (not signed in): the look's own card, title and words.
// The card picture is ./opengraph-image.tsx.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const post = await loadSharePreview(id);
  if (!post) return { title: "Community look", robots: PRIVATE_PAGE };
  const { title, description } = shareWords(post);
  return {
    title,
    description,
    robots: PRIVATE_PAGE,
    openGraph: { title, description, type: "article", url: `/community/post/${id}`, siteName: "TryOnU" },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function CommunityPostPage({ params }: Props) {
  const { id } = await params;
  return (
    <SiteChrome>
      <PostDetail id={id} />
    </SiteChrome>
  );
}
