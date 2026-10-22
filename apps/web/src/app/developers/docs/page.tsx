import Link from "next/link";
import { DevChrome } from "@/components/developers/DevChrome";
import { DeveloperDocs } from "@/components/developers/DeveloperDocs";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Virtual Try-On API Docs, Widget & Plugins",
  description:
    "Add AI virtual try-on to any app or online store: REST API with code for cURL, JavaScript, Python and PHP, a one-line website widget, Shopify and WooCommerce.",
  path: "/developers/docs",
  keywords: ["virtual try on API", "try on widget", "WooCommerce try on plugin"],
});

const SIDEBAR: { title: string; links: [string, string][] }[] = [
  { title: "Get started", links: [["Quick start", "#how-it-works"], ["Create an account", "/developers/sign-up"]] },
  { title: "No code", links: [["Website widget", "#widget"], ["Shopify", "#widget"], ["WordPress / WooCommerce", "#widget"]] },
  { title: "Server API", links: [["Code examples", "#code"], ["Reference", "#reference"], ["Responses", "#responses"], ["Errors", "#errors"]] },
  { title: "Account", links: [["Console", "/developers/console"], ["API keys", "/developers/console#keys"], ["Buy credits", "/developers/console#credits"]] },
];

export default function DeveloperDocsPage() {
  return (
    <DevChrome>
      <div className="mx-auto grid w-[min(1280px,calc(100%-32px))] gap-10 py-10 lg:grid-cols-[230px_minmax(0,1fr)] lg:py-14">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <nav aria-label="Docs" className="flex gap-6 overflow-x-auto pb-2 lg:block lg:space-y-7 lg:overflow-visible lg:pb-0">
            {SIDEBAR.map((g) => (
              <div key={g.title} className="shrink-0">
                <p className="font-mono text-[12px] font-semibold uppercase tracking-[0.12em] text-faint">{g.title}</p>
                <ul className="mt-2.5 flex gap-4 lg:block lg:space-y-1.5">
                  {g.links.map(([label, href]) => (
                    <li key={label}>
                      <Link href={href} className="whitespace-nowrap text-[14.5px] text-ink-soft hover:text-sage-deep">
                        {label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </aside>
        <div className="min-w-0">
          <p className="font-mono text-[12.5px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Documentation</p>
          <h1 className="mt-2 text-[clamp(30px,4.4vw,46px)] font-semibold leading-tight tracking-[-0.02em] text-ink">Virtual try-on API</h1>
          <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-muted">
            Show your customers wearing your clothes, shoes and jewellery on their own photo, on your website or in your app. Use the REST API
            from any language, or add a no-code button to your shop.
          </p>
          <div className="mt-8">
            <DeveloperDocs />
          </div>
        </div>
      </div>
    </DevChrome>
  );
}
