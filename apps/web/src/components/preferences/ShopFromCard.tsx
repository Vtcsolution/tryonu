"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShopFromChoices } from "@/components/auth/CountryGate";
import { preferences } from "@/lib/api/endpoints";
import type { ShopFrom } from "@/lib/api/types";
import { useSession } from "@/lib/auth/useSession";

/** "Where I shop" on My size & style: change the choice made after signing up. */
export function ShopFromCard() {
  const { user } = useSession();
  const qc = useQueryClient();
  const prefs = useQuery({ queryKey: ["preferences"], queryFn: preferences.get, enabled: !!user });
  const save = useMutation({
    mutationFn: (shop_from: ShopFrom) => preferences.update({ shop_from }),
    onSuccess: (p) => {
      qc.setQueryData(["preferences"], p);
      qc.invalidateQueries({ queryKey: ["search"] });
    },
  });
  if (!user || !prefs.data) return null;
  const value = (save.variables ?? prefs.data.shop_from ?? null) as ShopFrom | null;
  return (
    <section id="shop" className="tu-container scroll-mt-24 pb-6">
      <div className="mx-auto max-w-2xl rounded-[24px] border border-line bg-surface p-5 sm:p-6">
        <h2 className="text-[20px] font-semibold text-ink">Where I shop</h2>
        <p className="mt-1 text-[14.5px] text-muted">We show these shops first when you search.</p>
        <div className="mt-4">
          <ShopFromChoices value={value} onChange={(v) => save.mutate(v)} country={prefs.data.country} />
        </div>
        {save.isSuccess && <p className="mt-2 text-[14px] text-sage-deep">Saved ✓</p>}
        {save.isError && <p className="mt-2 text-[14px] text-[#a4553f]">Couldn&apos;t save. Please try again.</p>}
      </div>
    </section>
  );
}
