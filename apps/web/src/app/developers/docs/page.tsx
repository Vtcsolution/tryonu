import { SiteChrome } from "@/components/layout/SiteChrome";
import { DeveloperDocs } from "@/components/developers/DeveloperDocs";
import { Button } from "@/components/ui/Button";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Virtual Try-On API Docs, Widget & Plugins",
  description:
    "Add AI virtual try-on to any app or online store: REST API with code for cURL, JavaScript, Python and PHP, a one-line website widget, Shopify and WooCommerce.",
  path: "/developers/docs",
  keywords: ["virtual try on API", "try on widget", "WooCommerce try on plugin"],
});

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
