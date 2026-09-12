import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyEmailPanel } from "./VerifyEmailPanel";

export const metadata: Metadata = {
  title: "Verify your email",
  description: "Confirm your email to unlock your free TryOnU credits.",
};

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailPanel />
    </Suspense>
  );
}
