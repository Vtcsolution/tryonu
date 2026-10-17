import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { TryFlow } from "@/components/try/TryFlow";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Try it",
  description:
    "Build your fitting profile, pick a product, and see it rendered on you by AI — then shop the original listing.",
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
