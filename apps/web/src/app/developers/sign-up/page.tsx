import type { Metadata } from "next";
import { Suspense } from "react";
import { DeveloperSignUpForm } from "@/components/developers/DeveloperSignUpForm";

export const metadata: Metadata = {
  title: "Developer sign-up",
  description: "Create a TryOnU developer account to add virtual try-on to your shop or app.",
};

export default function DeveloperSignUpPage() {
  return (
    <Suspense>
      <DeveloperSignUpForm />
    </Suspense>
  );
}
