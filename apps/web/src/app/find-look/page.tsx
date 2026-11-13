import { Suspense } from "react";
import { FindLook } from "@/components/lens/FindLook";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Find an Outfit From a Picture and Try It On",
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
            <h1 className="font-display text-[clamp(30px,4.4vw,44px)] leading-tight text-ink">Find an outfit from a picture</h1>
            <p className="mx-auto mt-3 max-w-xl text-[17px] text-ink-soft">
              Upload a photo or screenshot of any outfit. TryOnU finds each piece (clothes, shoes, bags and jewellery) in real
              shops, shows the closest matches and lets you try them on your own photo.
            </p>
          </section>
        }
      >
        <FindLook />
      </Suspense>
      {/* in the page's HTML for search and AI answers; the tool above runs in the browser */}
      <section className="tu-container max-w-3xl pb-16">
        <h2 className="font-display text-[26px] text-ink">How to find an outfit from a picture</h2>
        <p className="mt-3 text-[17px] leading-relaxed text-ink-soft">
          Upload a photo or a screenshot of an outfit you like: from Instagram, TikTok, Pinterest, a magazine or a street-style
          picture you took yourself. TryOnU looks at each item in it (the coat, the top, the trousers, the shoes, the bag and the
          jewellery) and searches real shops for each one, showing exact matches where it finds them and the closest
          alternatives where it doesn&apos;t.
        </p>
        <p className="mt-3 text-[17px] leading-relaxed text-ink-soft">
          Then shop the look from the photo: put the pieces on your own photo to see the whole outfit on you, swap anything you
          don&apos;t like, and buy each piece from the shop that sells it, at its normal price. Products come from eBay, AliExpress,
          brand stores and shops that sell on TryOnU.
        </p>
        <h2 className="mt-10 font-display text-[26px] text-ink">Tips for the best matches</h2>
        <p className="mt-3 text-[17px] leading-relaxed text-ink-soft">
          Use a clear, well-lit picture where the outfit fills most of the frame. Crop out other people. If one piece matters most,
          for example the coat, crop the picture to that piece and search again. Searching is free; putting the outfit on your
          own photo is a try-on, which uses credits.
        </p>
      </section>
    </SiteChrome>
  );
}
