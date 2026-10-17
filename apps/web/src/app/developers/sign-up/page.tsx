import { Suspense } from "react";
import { DeveloperSignUpForm } from "@/components/developers/DeveloperSignUpForm";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Try-On API: Create a Developer Account",
  description:
    "Create a TryOnU developer account to add AI virtual try-on to your app or store. Prepaid credits, one credit per try-on, failed try-ons free.",
  path: "/developers/sign-up",
  keywords: ["virtual try on API sign up"],
});

export default function DeveloperSignUpPage() {
  return (
    <Suspense>
      <DeveloperSignUpForm />
    </Suspense>
  );
}
