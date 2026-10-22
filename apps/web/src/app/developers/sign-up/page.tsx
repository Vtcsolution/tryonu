import { Suspense } from "react";
import { DevChrome } from "@/components/developers/DevChrome";
import { DeveloperSignUpForm } from "@/components/developers/DeveloperSignUpForm";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Try-On API: Create a Developer Account",
  description:
    "Create a TryOnU developer account to add AI virtual try-on to your app or store. Prepaid credits, one credit per try-on, failed try-ons free.",
  path: "/developers/sign-up",
  keywords: ["virtual try on API sign up"],
});

const GETS: [string, string][] = [
  ["API keys", "A secret key for your server and website keys locked to your domains."],
  ["Website widget & plugins", "A “Try it on” button for any website, Shopify, WordPress and WooCommerce."],
  ["Pay per try-on", "Prepaid credits, one per try-on. Failed try-ons are free; credits never expire."],
  ["Usage & payments", "See every try-on and payment in your console."],
];

export default function DeveloperSignUpPage() {
  return (
    <DevChrome>
      <div className="mx-auto grid w-[min(1120px,calc(100%-32px))] items-start gap-12 py-12 md:py-16 lg:grid-cols-[1fr_440px]">
        <div className="lg:pt-6">
          <p className="font-mono text-[12.5px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Developer account</p>
          <h1 className="mt-2 text-[clamp(30px,4.4vw,44px)] font-semibold leading-tight tracking-[-0.02em] text-ink">
            Start building with the TryOnU API
          </h1>
          <p className="mt-3 max-w-xl text-[17px] leading-relaxed text-muted">Free to create. You only pay for the try-ons you use.</p>
          <ul className="mt-8 space-y-5">
            {GETS.map(([title, text]) => (
              <li key={title} className="flex gap-3.5">
                <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md bg-[#0d1210] text-[14px] text-[#b9cdb5]" aria-hidden="true">
                  ✓
                </span>
                <span>
                  <span className="block text-[16.5px] font-semibold text-ink">{title}</span>
                  <span className="block text-[15px] text-muted">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <Suspense>
          <DeveloperSignUpForm />
        </Suspense>
      </div>
    </DevChrome>
  );
}
