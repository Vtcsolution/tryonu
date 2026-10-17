import { ContentPage } from "@/components/content/ContentPage";
import { JsonLd, breadcrumbJsonLd, faqJsonLd } from "@/components/seo/JsonLd";
import { Button } from "@/components/ui/Button";
import { pageMeta } from "@/lib/seo";
import { ALL_FAQ, FAQ_GROUPS } from "@/lib/seoContent";

export const metadata = pageMeta({
  title: "TryOnU FAQ: Virtual Try-On, Credits, Shopping & Stores",
  description:
    "Answers about TryOnU: how to try clothes on your own photo, where to buy what you tried on, what it costs, photo privacy, selling as a shop and the try-on API.",
  path: "/faq",
  keywords: ["virtual try on FAQ", "how does virtual try on work", "where to buy outfit I tried on"],
});

export default function FaqPage() {
  return (
    <ContentPage
      kicker="Questions & answers"
      title="TryOnU FAQ"
      intro="Everything people ask about trying clothes on with AI, buying what you tried on, credits, privacy, and selling on TryOnU."
      narrow
    >
      <JsonLd data={[faqJsonLd(ALL_FAQ), breadcrumbJsonLd([{ name: "TryOnU", path: "/" }, { name: "FAQ", path: "/faq" }])]} />
      <div className="space-y-12">
        {FAQ_GROUPS.map((g) => (
          <section key={g.title}>
            <h2 className="font-display text-[28px] text-ink">{g.title}</h2>
            <div className="mt-4 divide-y divide-line rounded-[22px] border border-line bg-surface">
              {g.items.map((f) => (
                <div key={f.q} className="px-5 py-5">
                  <h3 className="text-[18px] font-semibold text-ink">{f.q}</h3>
                  <p className="mt-2 text-[16px] leading-relaxed text-ink-soft">{f.a}</p>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
      <div className="mt-12 flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-line bg-surface p-6">
        <p className="text-[17px] text-ink">Still have a question?</p>
        <div className="flex flex-wrap gap-3">
          <Button href="/try" size="md">Try it now</Button>
          <Button href="/contact" size="md" variant="outline">Contact us</Button>
        </div>
      </div>
    </ContentPage>
  );
}
