import type { ReferralSummary } from "@/lib/api/endpoints";

/** The share-and-earn rules in plain words, from the live settings. */
export function earnRuleLines(d: Pick<ReferralSummary, "tryon_credits" | "store_rewards" | "reward_credits">): string[] {
  const lines: string[] = [];
  if (d.tryon_credits > 0) {
    lines.push(
      `A friend joins from your link and tries something on: you get ${d.tryon_credits} credit${d.tryon_credits === 1 ? "" : "s"}.`,
    );
  }
  if (d.reward_credits > 0) {
    lines.push(`That friend buys credits for the first time: you get ${d.reward_credits} more.`);
  }
  if (d.store_rewards.length > 0) {
    const parts = d.store_rewards.map((r) => `${r.plan} ${r.credits}`).join(", ");
    lines.push(`A shop joins from your link and buys a store plan: you get ${parts} credits.`);
  }
  return lines;
}

/** A short, friendly list of the rules: easy to read at any age. */
export function EarnRules({ summary, compact = false }: { summary: ReferralSummary; compact?: boolean }) {
  const lines = earnRuleLines(summary);
  if (lines.length === 0) return null;
  return (
    <ul className={`space-y-2 ${compact ? "text-[14px]" : "text-[16px]"} leading-relaxed text-ink-soft`}>
      {lines.map((line) => (
        <li key={line} className="flex gap-2.5">
          <span
            aria-hidden="true"
            className={`mt-[3px] grid shrink-0 place-items-center rounded-full bg-sage font-bold text-white ${
              compact ? "h-[18px] w-[18px] text-[11px]" : "h-5 w-5 text-[12px]"
            }`}
          >
            +
          </span>
          <span>{line}</span>
        </li>
      ))}
    </ul>
  );
}
