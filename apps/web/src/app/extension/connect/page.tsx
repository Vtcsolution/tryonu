import type { Metadata } from "next";
import { Suspense } from "react";
import { ConnectExtension } from "@/components/extension/ConnectExtension";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Connect the TryOnU extension", robots: PRIVATE_PAGE };

export default function ConnectExtensionPage() {
  return (
    <SiteChrome>
      <Suspense>
        <ConnectExtension />
      </Suspense>
    </SiteChrome>
  );
}
