import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { SavedLooksGallery } from "@/components/saved/SavedLooksGallery";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Saved looks",
  description: "Your saved AI try-on results — revisit them or shop the original product.",
  robots: PRIVATE_PAGE,
};

export default function SavedPage() {
  return (
    <SiteChrome>
      <SavedLooksGallery />
    </SiteChrome>
  );
}
