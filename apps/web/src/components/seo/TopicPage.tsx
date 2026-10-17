import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ContentPage, InfoCard, SectionTitle, Steps } from "@/components/content/ContentPage";
import { JsonLd, breadcrumbJsonLd, faqJsonLd } from "@/components/seo/JsonLd";
import { Button } from "@/components/ui/Button";
import { SITE, pageMeta } from "@/lib/seo";
import { LANDINGS_BY_SLUG } from "@/lib/seoContent";

export function topicMetadata(slug: string): Metadata {
  const l = LANDINGS_BY_SLUG[slug];
  if (!l) return {};
  return pageMeta({ title: l.title, description: l.description, path: `/${l.slug}`, keywords: l.keywords });
}

/** A topic page (virtual try-on, bridal try-on, Shopify…): the direct answer
 * first, then benefits, steps, questions and a clear next step. */
export function TopicPage({ slug }: { slug: string }) {
  const l = LANDINGS_BY_SLUG[slug];
  if (!l) notFound();
  const related = l.related.map((s) => LANDINGS_BY_SLUG[s]).filter(Boolean);
  const structured: Record<string, unknown>[] = [
    faqJsonLd(l.faqs),
    breadcrumbJsonLd([
      { name: "TryOnU", path: "/" },
      { name: l.kicker, path: `/${l.slug}` },
    ]),
  ];
  if (l.audience === "shopper") {
    structured.push({
      "@context": "https://schema.org",
      "@type": "HowTo",
      name: l.h1,
      description: l.answer,
      totalTime: "PT2M",
      step: l.steps.map((s, i) => ({ "@type": "HowToStep", position: i + 1, name: s.title, text: s.text, url: `${SITE}${l.cta.href}` })),
    });
  }

  return (
    <ContentPage kicker={l.kicker} title={l.h1}>
      <JsonLd data={structured} />

      {/* the direct answer: what search and AI answers quote */}
      <div className="max-w-3xl rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6 md:p-8">
        <p className="text-[18.5px] leading-relaxed text-ink">{l.answer}</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button href={l.cta.href} size="lg">
            {l.cta.label} <span aria-hidden="true">→</span>
          </Button>
          <Button href={l.audience === "shopper" ? "/pricing" : "/developers/docs"} size="lg" variant="outline">
            {l.audience === "shopper" ? "See pricing" : "Read the docs"}
          </Button>
        </div>
      </div>

      <div className="mt-14">
        <SectionTitle>Why use TryOnU</SectionTitle>
        <div className="grid gap-5 md:grid-cols-3">
          {l.benefits.map((b) => (
            <InfoCard key={b.title} title={b.title}>
              {b.text}
            </InfoCard>
          ))}
        </div>
      </div>

      <div className="mt-14">
        <SectionTitle>How it works</SectionTitle>
        <Steps steps={l.steps} />
      </div>

      <div className="mt-14 max-w-3xl">
        <SectionTitle>Questions</SectionTitle>
        <div className="divide-y divide-line rounded-[22px] border border-line bg-surface">
          {l.faqs.map((f) => (
            <details key={f.q} className="group px-5 py-4" open>
              <summary className="cursor-pointer list-none text-[17px] font-semibold text-ink">
                <h3 className="inline">{f.q}</h3>
              </summary>
              <p className="mt-2 text-[16px] leading-relaxed text-ink-soft">{f.a}</p>
            </details>
          ))}
        </div>
        <p className="mt-3 text-[15px] text-muted">
          More answers in the <Link href="/faq" className="text-sage-deep underline">TryOnU FAQ</Link>.
        </p>
      </div>

      {related.length > 0 && (
        <div className="mt-14">
          <SectionTitle>Related</SectionTitle>
          <div className="flex flex-wrap gap-3">
            {related.map((r) => (
              <Link
                key={r.slug}
                href={`/${r.slug}`}
                className="rounded-full border border-line-strong px-4 py-2 text-[15px] font-medium text-ink hover:border-ink/40"
              >
                {r.kicker} →
              </Link>
            ))}
          </div>
        </div>
      )}
    </ContentPage>
  );
}
