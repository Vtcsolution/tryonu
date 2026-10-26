import { Suspense } from "react";
import { SignUpForm } from "./SignUpForm";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Create Your Free TryOnU Account",
  description:
    "Create a free TryOnU account to try real clothes, shoes and accessories on your own photo with AI, save looks and shop the original stores.",
  path: "/sign-up",
  keywords: [],
});

export default function SignUpPage() {
  return (
    <Suspense
      fallback={
        <section className="mx-auto max-w-md px-4 py-16 text-center">
          <h1 className="font-display text-[34px] leading-tight text-ink">Create your free TryOnU account</h1>
          <p className="mt-3 text-[16px] text-ink-soft">
            Add one photo of yourself and see real clothes, shoes and jewellery on you before you buy. Free to join.
          </p>
        </section>
      }
    >
      <SignUpForm />
    </Suspense>
  );
}
