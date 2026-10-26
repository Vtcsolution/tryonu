import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { TryFlow } from "@/components/try/TryFlow";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Try it",
  description:
    "Add your photo, pick a product or a ready look, and see it on you with AI. Then buy from the shop itself.",
  robots: PRIVATE_PAGE,
};

export default function TryPage() {
  return (
    <SiteChrome>
      <Suspense>
        <TryFlow />
      </Suspense>
    </SiteChrome>
  );
}
