"use client";

import { useState } from "react";
import { CompareSlider, type LookId } from "@/components/marketing/CompareSlider";

const TABS: [LookId, string][] = [
  ["women", "Women"],
  ["men", "Men"],
  ["kids", "Kids"],
];

/** The before/after slider with Women / Men / Kids tabs (winter looks). */
export function ShowcaseTabs({ initial = "women" }: { initial?: LookId }) {
  const [look, setLook] = useState<LookId>(initial);
  return (
    <div>
      <div role="tablist" aria-label="Choose a look" className="mx-auto mb-5 flex w-fit rounded-full border border-line bg-surface p-1">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={look === id}
            onClick={() => setLook(id)}
            className={`min-h-[42px] rounded-full px-5 text-[15px] font-semibold transition-colors ${
              look === id ? "bg-sage text-white" : "text-ink-soft hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <CompareSlider key={look} look={look} />
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
