import type { Metadata } from "next";
import { Suspense } from "react";
import { SignInForm } from "./SignInForm";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your TryOnU account.",
  robots: PRIVATE_PAGE,
};

export default function SignInPage() {
  return (
    <Suspense>
      <SignInForm />
    </Suspense>
  );
}
