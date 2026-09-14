import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyEmailPanel } from "./VerifyEmailPanel";

export const metadata: Metadata = {
  title: "Verify your email",
  description: "Confirm your email address to secure your TryOnU account.",
};

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailPanel />
    </Suspense>
  );
}
