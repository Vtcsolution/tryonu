import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { SavedLookDetail } from "@/components/saved/SavedLookDetail";

export const metadata: Metadata = { title: "Saved look", robots: { index: false, follow: false } };

type Props = { params: Promise<{ id: string }> };

export default async function SavedLookPage({ params }: Props) {
  const { id } = await params;
  return (
    <SiteChrome>
      <SavedLookDetail id={id} />
    </SiteChrome>
  );
}
