"use client";

import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import { CompareSlider, type LookId } from "@/components/marketing/CompareSlider";
import { Button } from "@/components/ui/Button";

const TABS: [LookId, string][] = [
  ["women", "Women"],
  ["men", "Men"],
  ["kids", "Kids"],
];

/** Women, men and kids side by side, each its own before/after slider with its
 * live products (home page). On phones they sit in one row you swipe through. */
export function ShowcaseRow() {
  return (
    <div>
      <p className="mb-3 text-center text-[14px] text-muted md:hidden">Swipe to see Women, Men and Kids</p>
      <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 md:mx-0 md:grid md:grid-cols-3 md:gap-6 md:overflow-visible md:px-0">
        {TABS.map(([id, label]) => (
          <div key={id} className="w-[85%] shrink-0 snap-center md:w-auto">
            <h3 className="mb-3 text-center font-display text-[24px] text-ink">{label}</h3>
            <CompareSlider look={id} compact />
          </div>
        ))}
      </div>
      <p className="mt-6 text-center text-[13.5px] text-muted">
        Real TryOnU try-ons of real shop products, shown on AI-generated models. Prices come live from the shops.
      </p>
      <div className="mx-auto mt-4 grid max-w-[560px] gap-3">
        <FirstOutfitOffer className="w-full" />
        <Button href="/try" size="lg" variant="outline" className="w-full">
          Try it on yourself <span aria-hidden="true">→</span>
        </Button>
      </div>
    </div>
  );
}

const TITLES: Record<LookId, string> = {
  women: "A women's winter look",
  men: "A men's winter look",
  kids: "A kids' winter look",
};

/** One look as its own section on a page: a heading, the slider and its live products. */
export function ShowcaseSection({ look, className = "" }: { look: LookId; className?: string }) {
  return (
    <section className={className} aria-label={TITLES[look]}>
      <p className="text-center text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Real try-on, real products</p>
      <h2 className="mt-1 text-center font-display text-[clamp(26px,3.6vw,36px)] leading-tight text-ink">
        {TITLES[look]}, <em>before and after</em>
      </h2>
      <div className="mt-6">
        <CompareSlider look={look} />
      </div>
    </section>
  );
}
