import { Reveal } from "@/components/ui/Reveal";
import { NOT_A_SHOP, PLAIN_STEPS, PRODUCT_SOURCES } from "@/lib/howItWorks";
import { Section, SectionHead } from "./primitives";

/** Home page: how TryOnU works and where the products come from, in plain words. */
export function HowItWorks() {
  return (
    <Section id="how" className="bg-paper-2">
      <SectionHead
        kicker="How it works"
        title={
          <>
            Four easy steps. <em>That&rsquo;s it.</em>
          </>
        }
        sub="From your photo to the shop, in about a minute."
      />

      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {PLAIN_STEPS.map((s, i) => (
          <li key={s.title} className="list-none">
            <Reveal delay={i * 80} className="h-full rounded-[22px] border border-line bg-surface p-5">
              <span className="grid h-10 w-10 place-items-center rounded-full bg-sage text-[17px] font-semibold text-white" aria-hidden="true">
                {i + 1}
              </span>
              <h3 className="mt-3 text-[18px] font-semibold leading-snug text-ink">{s.title}</h3>
              <p className="mt-1.5 text-[15.5px] leading-relaxed text-ink-soft">{s.text}</p>
            </Reveal>
          </li>
        ))}
      </ol>

      <Reveal className="mt-8 rounded-[24px] border border-line bg-surface p-5 md:p-7">
        <h3 className="font-display text-[24px] leading-tight text-ink">Where do the products come from?</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {PRODUCT_SOURCES.map((s) => (
            <div key={s.title} className="rounded-[16px] bg-paper-2 p-4">
              <p className="text-[16.5px] font-semibold text-ink">{s.title}</p>
              <p className="mt-1 text-[15px] leading-relaxed text-ink-soft">{s.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-[15.5px] font-medium text-ink">{NOT_A_SHOP}</p>
        <p className="mt-2 text-[15px] text-muted">
          Have a shop? <a href="/sell" className="text-sage-deep underline">Sell on TryOnU</a>. Have a website?{" "}
          <a href="/developers" className="text-sage-deep underline">Add a Try it on button</a>.
        </p>
      </Reveal>

      <Reveal className="mt-8 flex justify-center">
        <a
          href="/how-it-works"
          className="group inline-flex items-center gap-2 font-display text-[16px] text-sage transition-colors hover:text-sage-deep"
        >
          See the full guide <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">→</span>
        </a>
      </Reveal>
    </Section>
  );
}
