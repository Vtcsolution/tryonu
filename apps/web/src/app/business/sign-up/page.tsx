import type { Metadata } from "next";
import { Suspense } from "react";
import { StoreSignUpForm } from "@/components/business/StoreSignUpForm";

export const metadata: Metadata = {
  title: "Open your store",
  description: "Create a store account on TryOnU: list your products where shoppers try them on before they buy.",
};

export default function StoreSignUpPage() {
  return (
    <Suspense>
      <StoreSignUpForm />
    </Suspense>
  );
}
