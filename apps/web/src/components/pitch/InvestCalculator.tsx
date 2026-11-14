"use client";

import { useState } from "react";

/**
 * The 2027 goal on /invest: four sliders (paying shoppers, stores, API
 * clients, shop-link sales) and the revenue they add up to, per stream.
 * Starting values are the founder's target; investors can move them.
 * Clearly a goal, not a forecast.
 */

type Lever = {
  key: string;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
  start: number;
  /** monthly revenue from this lever's value */
  revenue: (v: number) => number;
  how: string;
  color: string;
};

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

export function InvestCalculator({
  shopperSpend,
  storePlan,
  apiPack,
  commission = 0.04,
}: {
  /** average spend of a paying shopper per month, in dollars */
  shopperSpend: number;
  /** average store plan per month, in dollars */
  storePlan: number;
  /** average API pack per client per month, in dollars */
  apiPack: number;
  /** share of each shop-link sale TryOnU earns */
  commission?: number;
}) {
  const levers: Lever[] = [
    {
      key: "shoppers",
      label: "Paying shoppers a month",
      unit: "shoppers",
      min: 0,
      max: 20000,
      step: 250,
      start: 2500,
      revenue: (v) => v * shopperSpend,
      how: `${usd(shopperSpend)} average credit pack each`,
      color: "#3d8547",
    },
    {
      key: "stores",
      label: "Stores on a monthly plan",
      unit: "stores",
      min: 0,
      max: 3000,
      step: 25,
      start: 400,
      revenue: (v) => v * storePlan,
      how: `${usd(storePlan)} average plan each`,
      color: "#c9a13b",
    },
    {
      key: "api",
      label: "Companies using the API",
      unit: "companies",
      min: 0,
      max: 300,
      step: 5,
      start: 25,
      revenue: (v) => v * apiPack,
      how: `${usd(apiPack)} average pack each a month`,
      color: "#4a7fb5",
    },
    {
      key: "affiliate",
      label: "Sales through shop links a month",
      unit: "dollars",
      min: 0,
      max: 1000000,
      step: 10000,
      start: 150000,
      revenue: (v) => v * commission,
      how: `about ${Math.round(commission * 100)}% commission on each sale`,
      color: "#b4483a",
    },
  ];
  const [values, setValues] = useState<Record<string, number>>(Object.fromEntries(levers.map((l) => [l.key, l.start])));
  const parts = levers.map((l) => ({ ...l, value: values[l.key], monthly: l.revenue(values[l.key]) }));
  const monthly = parts.reduce((n, p) => n + p.monthly, 0);
  const top = Math.max(...parts.map((p) => p.monthly), 1);

  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
      <div className="space-y-5 rounded-[26px] border border-line bg-surface p-6">
        {parts.map((p) => (
          <label key={p.key} className="block">
            <span className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-[16px] font-semibold text-ink">{p.label}</span>
              <span className="font-display text-[22px] text-ink">
                {p.key === "affiliate" ? usd(p.value) : p.value.toLocaleString("en-US")}
              </span>
            </span>
            <input
              type="range"
              min={p.min}
              max={p.max}
              step={p.step}
              value={p.value}
              onChange={(e) => setValues((v) => ({ ...v, [p.key]: Number(e.target.value) }))}
              className="mt-2 w-full"
              style={{ accentColor: p.color }}
              aria-label={p.label}
            />
            <span className="text-[13.5px] text-muted">{p.how}</span>
          </label>
        ))}
        <button
          type="button"
          onClick={() => setValues(Object.fromEntries(levers.map((l) => [l.key, l.start])))}
          className="text-[14px] font-semibold text-sage-deep hover:underline"
        >
          Back to our target
        </button>
      </div>

      <div className="flex flex-col rounded-[26px] bg-[#16231a] p-6 text-white">
        <p className="text-[13px] font-bold uppercase tracking-[0.14em] text-[#9fd49a]">Revenue by December 2027</p>
        <p className="mt-2 font-display text-[clamp(40px,6vw,60px)] leading-none">{usd(monthly)}</p>
        <p className="text-[16px] text-white/80">a month</p>
        <p className="mt-3 font-display text-[28px] leading-none text-[#9fd49a]">{usd(monthly * 12)}</p>
        <p className="text-[15px] text-white/80">a year at that pace</p>
        <ul className="mt-6 space-y-3">
          {parts.map((p) => (
            <li key={p.key}>
              <span className="flex justify-between text-[14.5px]">
                <span>{p.label.replace(" a month", "").replace("Sales through shop links", "Affiliate")}</span>
                <b>{usd(p.monthly)}</b>
              </span>
              <span className="mt-1 block h-2.5 overflow-hidden rounded-full bg-white/10">
                <span
                  className="block h-full rounded-full transition-[width] duration-500"
                  style={{ width: `${(p.monthly / top) * 100}%`, backgroundColor: p.color }}
                />
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-auto pt-6 text-[13px] leading-relaxed text-white/70">
          Our goal, not a forecast. Move the sliders to see how each part adds up. Prices are TryOnU&apos;s live prices today.
        </p>
      </div>
    </div>
  );
}
