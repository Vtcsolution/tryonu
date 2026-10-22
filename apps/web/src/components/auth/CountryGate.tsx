"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { auth, preferences } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

// pages where asking would be in the way (signing in, resetting a password)
const SKIP = ["/sign-in", "/sign-up", "/forgot-password", "/reset-password", "/verify-email", "/business/sign-up", "/developers"];

/**
 * One short screen for anyone signed in without a country (e.g. just signed
 * up with Google): the country decides which shops and deliveries they see.
 * Pre-filled from where they are, so most people only press Continue.
 */
export function CountryGate() {
  const pathname = usePathname() ?? "";
  const { user } = useSession();
  const qc = useQueryClient();
  const skip = SKIP.some((p) => pathname.startsWith(p));
  const prefs = useQuery({ queryKey: ["preferences"], queryFn: preferences.get, enabled: !!user && !skip });
  const missing = !!user && !skip && prefs.isSuccess && !prefs.data?.country;
  const hint = useQuery({ queryKey: ["country-hint"], queryFn: auth.countryHint, enabled: missing, staleTime: Infinity, retry: false });
  const [country, setCountry] = useState("");

  useEffect(() => {
    if (hint.data?.country && !country) setCountry(hint.data.country);
  }, [hint.data, country]);

  const save = useMutation({
    mutationFn: () => preferences.update({ country }),
    onSuccess: (p) => qc.setQueryData(["preferences"], p),
  });

  if (!missing) return null;
  return (
    <div className="fixed inset-0 z-[70] grid place-items-center bg-black/60 px-4 backdrop-blur-[2px]">
      <div role="dialog" aria-modal="true" aria-labelledby="country-gate-title" className="w-full max-w-md rounded-[24px] border border-line bg-surface p-6 shadow-lift">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">One last step</p>
        <h2 id="country-gate-title" className="mt-1 font-display text-[26px] leading-tight text-ink">
          Where do you live?
        </h2>
        <p className="mt-2 text-[15.5px] text-muted">So we show you shops that deliver to you, local shops first.</p>
        <form
          className="mt-5 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (country) save.mutate();
          }}
        >
          <CountryPicker value={country} onChange={setCountry} suggested={hint.data?.country} />
          {save.isError && <p role="alert" className="text-[14px] text-[#a4553f]">Couldn&apos;t save. Please try again.</p>}
          <Button type="submit" size="md" className="w-full" disabled={!country || save.isPending}>
            {save.isPending ? "Saving…" : "Continue"} {!save.isPending && <span aria-hidden="true">→</span>}
          </Button>
        </form>
      </div>
    </div>
  );
}
