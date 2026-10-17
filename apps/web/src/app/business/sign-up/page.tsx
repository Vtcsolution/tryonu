import { Suspense } from "react";
import { StoreSignUpForm } from "@/components/business/StoreSignUpForm";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Open Your Store on TryOnU",
  description:
    "Create your store on TryOnU in minutes: add your products, choose a plan and let shoppers near you try your products on before they buy.",
  path: "/business/sign-up",
  keywords: ["open online clothing store", "sell on TryOnU"],
});

export default function StoreSignUpPage() {
  return (
    <Suspense>
      <StoreSignUpForm />
    </Suspense>
  );
}
