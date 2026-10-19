import type { Metadata } from "next";
import { SavedPosts } from "@/components/community/SavedPosts";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Saved posts", robots: PRIVATE_PAGE };

export default function SavedPostsPage() {
  return (
    <SiteChrome>
      <SavedPosts />
    </SiteChrome>
  );
}
