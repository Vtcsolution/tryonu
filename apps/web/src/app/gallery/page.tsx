import type { Metadata } from "next";
import { GalleryPage } from "@/components/gallery/GalleryPage";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "My looks",
  description: "Every look you've tried on with TryOnU.",
  robots: PRIVATE_PAGE,
};

export default function Page() {
  return (
    <SiteChrome>
      <GalleryPage />
    </SiteChrome>
  );
}
