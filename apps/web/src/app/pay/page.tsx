import type { Metadata } from "next";
import { Suspense } from "react";
import { PaddleCheckout } from "@/components/credits/PaddleCheckout";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Secure checkout", robots: PRIVATE_PAGE };

export default function PayPage() {
  return (
    <SiteChrome>
      <Suspense>
        <PaddleCheckout />
      </Suspense>
    </SiteChrome>
  );
}
