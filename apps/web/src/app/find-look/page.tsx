import { Suspense } from "react";
import { FindLook } from "@/components/lens/FindLook";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Find the Look: Search Clothes by Photo",
  description:
    "Upload a photo or screenshot of any outfit. TryOnU finds each item (clothes, shoes, bags, jewellery) in real shops, then lets you try them on.",
  path: "/find-look",
  keywords: ["search clothes by photo", "find outfit from picture", "shop the look", "visual search fashion", "find dress from photo"],
});

export default function FindLookPage() {
  return (
    <SiteChrome>
      <Suspense
        fallback={
          <section className="tu-container py-12 text-center">
            <h1 className="font-display text-[clamp(30px,4.4vw,44px)] leading-tight text-ink">Find the look from a photo</h1>
            <p className="mx-auto mt-3 max-w-xl text-[17px] text-ink-soft">
              Upload a photo or screenshot of any outfit. TryOnU finds each piece (clothes, shoes, bags and jewellery) in real
              shops, shows the closest matches and lets you try them on your own photo.
            </p>
          </section>
        }
      >
        <FindLook />
      </Suspense>
    </SiteChrome>
  );
}
