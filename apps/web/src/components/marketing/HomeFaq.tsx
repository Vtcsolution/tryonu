import Link from "next/link";
import { JsonLd, faqJsonLd } from "@/components/seo/JsonLd";
import { SITE_DEFINITION } from "@/lib/seo";
import { HOME_FAQ, LANDINGS } from "@/lib/seoContent";
import { Section, SectionHead } from "./primitives";

/** The questions people ask most, answered directly: for visitors, search
 * snippets and AI answers alike. */
export function HomeFaq() {
  return (
    <Section id="faq">
      <JsonLd data={faqJsonLd(HOME_FAQ)} />
      <SectionHead
        align="center"
        kicker="Questions"
        title={
          <>
            Good to <em>know</em>
          </>
        }
        sub={SITE_DEFINITION}
      />
      <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-2">
        {HOME_FAQ.map((f) => (
          <div key={f.q} className="rounded-[22px] border border-line bg-surface p-6">
            <h3 className="text-[18px] font-semibold text-ink">{f.q}</h3>
            <p className="mt-2 text-[15.5px] leading-relaxed text-ink-soft">{f.a}</p>
          </div>
        ))}
      </div>
      <div className="mx-auto mt-8 max-w-5xl text-center">
        <Link href="/faq" className="text-[16px] font-semibold text-sage-deep hover:underline">
          All questions and answers →
        </Link>
        <p className="mt-6 text-[14.5px] text-muted">Popular:</p>
        <div className="mt-2 flex flex-wrap justify-center gap-2">
          {LANDINGS.filter((l) => l.audience === "shopper").map((l) => (
            <Link
              key={l.slug}
              href={`/${l.slug}`}
              className="rounded-full border border-line px-3.5 py-1.5 text-[14px] text-ink-soft hover:border-line-strong hover:text-ink"
            >
              {l.kicker}
            </Link>
          ))}
        </div>
      </div>
    </Section>
  );
}
