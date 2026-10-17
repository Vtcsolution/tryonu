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
    <Suspense>
      <SignUpForm />
    </Suspense>
  );
}
