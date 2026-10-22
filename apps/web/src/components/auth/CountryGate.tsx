"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { auth, preferences } from "@/lib/api/endpoints";
import type { ShopFrom } from "@/lib/api/types";
import { useSession } from "@/lib/auth/useSession";
import { countryName } from "@/lib/countries";

// pages where asking would be in the way (signing in, resetting a password)
const SKIP = ["/sign-in", "/sign-up", "/forgot-password", "/reset-password", "/verify-email", "/business/sign-up", "/developers", "/admin"];

export function shopChoices(country: string | null | undefined): { id: ShopFrom; icon: string; title: string; text: string }[] {
  const where = country ? countryName(country) : "your country";
  return [
    { id: "local", icon: "🏠", title: "Local shops", text: `Brands and shops in ${where}. Faster, easier delivery.` },
    { id: "worldwide", icon: "🌍", title: "Worldwide stores", text: "Big international websites, shipping to you." },
    { id: "both", icon: "✨", title: "Both", text: "Show me everything, local shops first." },
  ];
}

/** The three big choices: where they like to shop. */
export function ShopFromChoices({ value, onChange, country }: { value: ShopFrom | null; onChange: (v: ShopFrom) => void; country?: string | null }) {
  return (
    <div role="radiogroup" aria-label="Where do you like to shop?" className="grid gap-2">
      {shopChoices(country).map((c) => (
        <button
          key={c.id}
          type="button"
          role="radio"
          aria-checked={value === c.id}
          onClick={() => onChange(c.id)}
          className={`tu-tap flex items-center gap-3 rounded-2xl border p-3.5 text-left transition-colors ${
            value === c.id ? "border-sage bg-sage/10" : "border-line hover:border-line-strong"
          }`}
        >
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-paper-2 text-[22px]" aria-hidden="true">
            {c.icon}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[16px] font-semibold text-ink">{c.title}</span>
            <span className="block text-[13.5px] leading-snug text-muted">{c.text}</span>
          </span>
          <span
            className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 ${value === c.id ? "border-sage bg-sage text-white" : "border-line-strong"}`}
            aria-hidden="true"
          >
            {value === c.id && "✓"}
          </span>
        </button>
      ))}
    </div>
  );
}

/**
 * One short screen for anyone signed in who hasn't told us their country (e.g.
 * just signed up with Google) or where they like to shop: local shops, worldwide
 * stores, or both. The country is pre-filled from where they are.
 */
export function CountryGate() {
  const pathname = usePathname() ?? "";
  const { user } = useSession();
  const qc = useQueryClient();
  const skip = SKIP.some((p) => pathname.startsWith(p));
  const prefs = useQuery({ queryKey: ["preferences"], queryFn: preferences.get, enabled: !!user && !skip });
  const needCountry = !!user && !skip && prefs.isSuccess && !prefs.data?.country;
  const needShop = !!user && !skip && prefs.isSuccess && !prefs.data?.shop_from;
  const hint = useQuery({ queryKey: ["country-hint"], queryFn: auth.countryHint, enabled: needCountry, staleTime: Infinity, retry: false });
  const [country, setCountry] = useState("");
  const [shop, setShop] = useState<ShopFrom | null>(null);

  useEffect(() => {
    if (hint.data?.country && !country) setCountry(hint.data.country);
  }, [hint.data, country]);

  const save = useMutation({
    mutationFn: () => preferences.update({ ...(needCountry ? { country } : {}), ...(needShop && shop ? { shop_from: shop } : {}) }),
    onSuccess: (p) => qc.setQueryData(["preferences"], p),
  });

  if (!needCountry && !needShop) return null;
  const ready = (!needCountry || !!country) && (!needShop || !!shop);
  return (
    <div className="fixed inset-0 z-[70] grid place-items-center overflow-y-auto bg-black/60 px-4 py-6 backdrop-blur-[2px]">
      <div role="dialog" aria-modal="true" aria-labelledby="country-gate-title" className="w-full max-w-md rounded-[24px] border border-line bg-surface p-6 shadow-lift">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">One last step</p>
        <h2 id="country-gate-title" className="mt-1 font-display text-[26px] leading-tight text-ink">
          {needCountry ? "Where do you live?" : "Where do you like to shop?"}
        </h2>
        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (ready) save.mutate();
          }}
        >
          {needCountry && <CountryPicker value={country} onChange={setCountry} suggested={hint.data?.country} />}
          {needShop && (
            <div>
              {needCountry && <p className="mb-2 text-[16px] font-semibold text-ink">Where do you like to shop?</p>}
              <ShopFromChoices value={shop} onChange={setShop} country={country || prefs.data?.country} />
              <p className="mt-2 text-[13px] text-muted">You can change this any time in My size & style.</p>
            </div>
          )}
          {save.isError && <p role="alert" className="text-[14px] text-[#a4553f]">Couldn&apos;t save. Please try again.</p>}
          <Button type="submit" size="md" className="w-full" disabled={!ready || save.isPending}>
            {save.isPending ? "Saving…" : "Continue"} {!save.isPending && <span aria-hidden="true">→</span>}
          </Button>
        </form>
      </div>
    </div>
  );
}
