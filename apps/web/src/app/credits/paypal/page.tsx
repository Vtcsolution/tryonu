import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PayPalReturn } from "@/components/credits/PayPalReturn";

export const metadata: Metadata = {
  title: "Payment",
  description: "Confirming your TryOnU credit purchase.",
  robots: { index: false },
};

export default function PayPalReturnPage() {
  return (
    <SiteChrome>
      <Suspense>
        <PayPalReturn />
      </Suspense>
    </SiteChrome>
  );
}
