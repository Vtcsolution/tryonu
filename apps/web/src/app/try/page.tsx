import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { TryFlow } from "@/components/try/TryFlow";

export const metadata: Metadata = {
  title: "Try it",
  description:
    "Build your fitting profile, pick a product, and see it rendered on you by AI — then shop the original listing.",
};

export default function TryPage() {
  return (
    <SiteChrome>
      <TryFlow />
    </SiteChrome>
  );
}
