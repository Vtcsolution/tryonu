"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { TagInput } from "@/components/ui/TagInput";
import { ApiError } from "@/lib/api/client";
import { preferences as preferencesApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { Gender, UserPreference } from "@/lib/api/types";

const GENDERS: { value: Gender | null; label: string }[] = [
  { value: null, label: "Not set" },
  { value: "women", label: "Women" },
  { value: "men", label: "Men" },
  { value: "unisex", label: "Unisex" },
  { value: "kids", label: "Kids" },
];

export function PreferencesForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, isLoading: sessionLoading } = useSession();

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/preferences");
  }, [sessionLoading, user, router]);

  const prefQuery = useQuery({
    queryKey: ["preferences"],
    queryFn: preferencesApi.get,
    enabled: !!user,
  });

  const [gender, setGender] = useState<Gender | null>(null);
  const [sizes, setSizes] = useState<string[]>([]);
  const [colors, setColors] = useState<string[]>([]);
  const [styles, setStyles] = useState<string[]>([]);
  const [brands, setBrands] = useState<string[]>([]);
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (prefQuery.data && !loaded) {
      const p = prefQuery.data;
      setGender(p.gender);
      setSizes(p.preferred_sizes ?? []);
      setColors(p.preferred_colors ?? []);
      setStyles(p.preferred_styles ?? []);
      setBrands(p.preferred_brands ?? []);
      setBudgetMin(p.budget_min_cents != null ? String(p.budget_min_cents / 100) : "");
      setBudgetMax(p.budget_max_cents != null ? String(p.budget_max_cents / 100) : "");
      setLoaded(true);
    }
  }, [prefQuery.data, loaded]);

  const save = useMutation({
    mutationFn: (payload: Partial<UserPreference>) => preferencesApi.update(payload),
    onSuccess: (data) => qc.setQueryData(["preferences"], data),
  });

  const onSubmit = () => {
    const min = budgetMin.trim() ? Math.round(Number(budgetMin) * 100) : null;
    const max = budgetMax.trim() ? Math.round(Number(budgetMax) * 100) : null;
    save.mutate({
      gender,
      preferred_sizes: sizes,
      preferred_colors: colors,
      preferred_styles: styles,
      preferred_brands: brands,
      budget_min_cents: Number.isFinite(min) ? min : null,
      budget_max_cents: Number.isFinite(max) ? max : null,
    });
  };

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(760px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(760px,calc(100%-42px))] py-14 md:py-20">
      <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
        Fashion <em>preferences</em>
      </h1>
      <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
        Helps the AI stylist and search tailor recommendations to you.
      </p>

      <div className="mt-8 space-y-8 rounded-[26px] border border-line bg-surface p-6 sm:p-8">
        <Field label="I usually shop for">
          <div className="flex flex-wrap gap-2">
            {GENDERS.map((g) => (
              <button
                key={g.label}
                type="button"
                onClick={() => setGender(g.value)}
                className={`rounded-full border px-3.5 py-1.5 text-[13px] transition-colors ${
                  gender === g.value
                    ? "border-sage bg-sage text-white"
                    : "border-line text-ink-soft hover:border-line-strong"
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </Field>

        <Field label="Sizes">
          <TagInput values={sizes} onChange={setSizes} placeholder="e.g. M, 32, 9.5 — press Enter" />
        </Field>

        <Field label="Favorite colors">
          <TagInput values={colors} onChange={setColors} placeholder="e.g. black, cream — press Enter" />
        </Field>

        <Field label="Preferred styles">
          <TagInput values={styles} onChange={setStyles} placeholder="e.g. casual, streetwear — press Enter" />
        </Field>

        <Field label="Favorite brands">
          <TagInput values={brands} onChange={setBrands} placeholder="e.g. Levi's, Zara — press Enter" />
        </Field>

        <Field label="Budget range">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[14px] text-faint">$</span>
              <input
                type="number"
                min={0}
                value={budgetMin}
                onChange={(e) => setBudgetMin(e.target.value)}
                placeholder="Min"
                className="h-11 w-full rounded-xl border border-line-strong bg-paper pl-7 pr-3.5 text-[14px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
              />
            </div>
            <span className="text-faint">–</span>
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[14px] text-faint">$</span>
              <input
                type="number"
                min={0}
                value={budgetMax}
                onChange={(e) => setBudgetMax(e.target.value)}
                placeholder="Max"
                className="h-11 w-full rounded-xl border border-line-strong bg-paper pl-7 pr-3.5 text-[14px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
              />
            </div>
          </div>
        </Field>

        {save.isError && (
          <p role="alert" className="text-[13px] text-[#a4553f]">
            {save.error instanceof ApiError ? save.error.detail : "Couldn't save your preferences."}
          </p>
        )}

        <Button size="md" className="w-full" disabled={save.isPending} onClick={onSubmit}>
          {save.isPending ? "Saving…" : save.isSuccess ? "Saved ✓" : "Save preferences"}
        </Button>
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <span className="mb-2 block text-[13px] font-medium text-ink-soft">{label}</span>
      {children}
    </div>
  );
}

