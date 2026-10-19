import { Suspense } from "react";
import { FindLook } from "@/components/lens/FindLook";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Find the Look: Search Clothes by Photo",
  description:
    "Upload a photo or screenshot of any outfit. TryOnU finds every item in it (clothes, shoes, bags, jewellery) in real shops, exact matches and the closest alternatives, then lets you try them on.",
  path: "/find-look",
  keywords: ["search clothes by photo", "find outfit from picture", "shop the look", "visual search fashion", "find dress from photo"],
});

export default function FindLookPage() {
  return (
    <SiteChrome>
      <Suspense fallback={<div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />}>
        <FindLook />
      </Suspense>
    </SiteChrome>
  );
}
