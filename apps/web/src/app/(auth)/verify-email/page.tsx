import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyEmailPanel } from "./VerifyEmailPanel";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Verify your email",
  description: "Confirm your email address to secure your TryOnU account.",
  robots: PRIVATE_PAGE,
};

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailPanel />
    </Suspense>
  );
}
