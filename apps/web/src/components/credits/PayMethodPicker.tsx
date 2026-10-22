"use client";

import { useEffect } from "react";
import { useGateways } from "@/lib/useCheckout";

/** "Pay with": shown only when more than one payment gateway is switched on in Admin.
 *  Keeps `value` on a gateway that is on (the default one first). */
export function PayMethodPicker({ value, onChange }: { value: string | null; onChange: (id: string) => void }) {
  const gateways = useGateways();
  useEffect(() => {
    if (gateways.length && !gateways.some((g) => g.id === value)) onChange(gateways[0].id);
  }, [gateways, value, onChange]);
  if (gateways.length < 2) return null;
  return (
    <div role="radiogroup" aria-label="Pay with" className="flex flex-wrap items-center gap-2">
      <span className="text-[14px] font-medium text-ink-soft">Pay with</span>
      {gateways.map((g) => (
        <button
          key={g.id}
          type="button"
          role="radio"
          aria-checked={value === g.id}
          onClick={() => onChange(g.id)}
          className={`min-h-[40px] rounded-full border px-4 text-[14px] font-semibold transition-colors ${
            value === g.id ? "border-sage bg-sage/10 text-ink" : "border-line text-ink-soft hover:border-line-strong"
          }`}
        >
          {g.label}
        </button>
      ))}
    </div>
  );
}
