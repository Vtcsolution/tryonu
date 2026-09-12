import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { SavedLooksGallery } from "@/components/saved/SavedLooksGallery";

export const metadata: Metadata = {
  title: "Saved looks",
  description: "Your saved AI try-on results — revisit them or shop the original product.",
};

export default function SavedPage() {
  return (
    <SiteChrome>
      <SavedLooksGallery />
    </SiteChrome>
  );
}
