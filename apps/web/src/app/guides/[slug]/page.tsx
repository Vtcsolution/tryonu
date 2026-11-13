import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ContentPage, SectionTitle } from "@/components/content/ContentPage";
import { LookCards } from "@/components/looks/LookCollectionPage";
import { JsonLd, breadcrumbJsonLd, faqJsonLd } from "@/components/seo/JsonLd";
import { Button } from "@/components/ui/Button";
import { GUIDES, GUIDES_BY_SLUG } from "@/lib/guides";
import { publishedLooks } from "@/lib/looks";
import { OWNER, SITE, pageMeta } from "@/lib/seo";
import { LANDINGS_BY_SLUG } from "@/lib/seoContent";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return GUIDES.map((g) => ({ slug: g.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const g = GUIDES_BY_SLUG[(await params).slug];
  if (!g) return { title: "Guide not found", robots: { index: false, follow: false } };
  return pageMeta({ title: g.title, description: g.description, path: `/guides/${g.slug}`, keywords: g.keywords });
}

/** /guides/<slug>: one article. The direct answer first, then the sections,
 * real looks, questions, and the landing page it supports. */
export default async function GuidePage({ params }: Props) {
  const g = GUIDES_BY_SLUG[(await params).slug];
  if (!g) notFound();
  const looks = g.looks
    ? (await publishedLooks())
        .filter((l) => (!g.looks!.season || l.season === g.looks!.season) && (!g.looks!.audience || l.audience === g.looks!.audience))
        .slice(0, g.looks.limit)
    : [];
  const landing = LANDINGS_BY_SLUG[g.landing.slug];
  const others = GUIDES.filter((x) => x.slug !== g.slug && x.audience === g.audience).slice(0, 3);
  const path = `/guides/${g.slug}`;

  return (
    <ContentPage kicker="Guide" title={g.h1}>
      <JsonLd
        data={[
          {
            "@context": "https://schema.org",
            "@type": "Article",
            headline: g.h1,
            description: g.description,
            url: `${SITE}${path}`,
            datePublished: g.published,
            dateModified: g.updated,
            inLanguage: "en-GB",
            author: { "@type": "Organization", name: "TryOnU", url: SITE },
            publisher: { "@id": `${SITE}/#organization` },
          },
          faqJsonLd(g.faqs),
          breadcrumbJsonLd([
            { name: "TryOnU", path: "/" },
            { name: "Guides", path: "/guides" },
            { name: g.h1, path },
          ]),
        ]}
      />

      <p className="text-[14px] text-muted">
        Updated {new Date(g.updated).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })} · TryOnU team
      </p>

      <div className="mt-4 max-w-3xl rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6 md:p-8">
        <p className="text-[18.5px] leading-relaxed text-ink">{g.answer}</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button href={g.audience === "shopper" ? "/try" : "/developers"} size="lg">
            {g.audience === "shopper" ? "Try it on now" : "Get started"} <span aria-hidden="true">→</span>
          </Button>
          {landing && (
            <Button href={`/${landing.slug}`} size="lg" variant="outline">
              {g.landing.label}
            </Button>
          )}
        </div>
      </div>

      <article className="max-w-3xl">
        {g.sections.map((s) => (
          <section key={s.h2} className="mt-12">
            <SectionTitle>{s.h2}</SectionTitle>
            {s.paragraphs.map((p) => (
              <p key={p} className="mt-3 text-[17px] leading-relaxed text-ink-soft">{p}</p>
            ))}
          </section>
        ))}
      </article>

      {looks.length > 0 && (
        <div className="mt-14">
          <SectionTitle>Looks to try on</SectionTitle>
          <LookCards looks={looks} />
        </div>
      )}

      <div className="mt-14 max-w-3xl">
        <SectionTitle>Questions</SectionTitle>
        <div className="divide-y divide-line rounded-[22px] border border-line bg-surface">
          {g.faqs.map((f) => (
            <details key={f.q} className="px-5 py-4" open>
              <summary className="cursor-pointer list-none text-[17px] font-semibold text-ink">
                <h3 className="inline">{f.q}</h3>
              </summary>
              <p className="mt-2 text-[16px] leading-relaxed text-ink-soft">{f.a}</p>
            </details>
          ))}
        </div>
      </div>

      <p className="mt-10 max-w-3xl text-[15px] text-muted">
        {g.audience === "shopper"
          ? "Your photo is used only to make your own try-ons and you can delete it at any time. "
          : "Shoppers' photos are used only for their own try-ons and can be deleted at any time. "}
        Read the <Link href="/photo-policy" className="text-sage-deep underline">photo policy</Link> and the{" "}
        <Link href="/privacy" className="text-sage-deep underline">privacy policy</Link>. TryOnU is run by {OWNER}.
      </p>

      {others.length > 0 && (
        <div className="mt-14">
          <SectionTitle>More guides</SectionTitle>
          <div className="flex flex-wrap gap-3">
            {others.map((o) => (
              <Link key={o.slug} href={`/guides/${o.slug}`} className="rounded-full border border-line-strong px-4 py-2 text-[15px] font-medium text-ink hover:border-ink/40">
                {o.h1} →
              </Link>
            ))}
          </div>
        </div>
      )}
    </ContentPage>
  );
}
