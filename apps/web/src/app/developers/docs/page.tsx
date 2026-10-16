import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { DeveloperDocs } from "@/components/developers/DeveloperDocs";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Try-on API for developers",
  description:
    "Add AI virtual try-on to your shop or app with TryOnU's API: code for cURL, JavaScript, Python, PHP and WordPress. Pay per try-on.",
};

export default function DeveloperDocsPage() {
  return (
    <SiteChrome>
      <section className="tu-container py-12 md:py-16">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">TryOnU for developers</p>
        <h1 className="mt-2 font-display text-[clamp(32px,5vw,52px)] leading-tight text-ink">
          Virtual try-on for <em>your</em> shop
        </h1>
        <p className="mt-4 max-w-2xl text-[17px] leading-relaxed text-muted">
          Let your customers see your clothes, shoes and jewellery on their own photo, on your website or app. One simple API that
          works from any language, and a WordPress example ready to paste. Pay only for the try-ons you use: from $0.50 each,
          credits never expire.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button href="/developers/sign-up" size="md">Get your API key <span aria-hidden="true">→</span></Button>
          <Button href="/developers" size="md" variant="outline">Developer portal</Button>
        </div>
        <div className="mt-10">
          <DeveloperDocs />
        </div>
      </section>
    </SiteChrome>
  );
}
