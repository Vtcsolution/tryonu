"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { TagInput, type TagSuggestion } from "@/components/ui/TagInput";
import { ApiError } from "@/lib/api/client";
import { catalog, preferences as preferencesApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { Gender, TaxonomyNode, UserPreference } from "@/lib/api/types";

const STEPS = ["You", "Categories", "Styles", "Details"] as const;

const CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "XXL", "3XL"];
const WOMEN_SHOE_SIZES = ["EU 36", "EU 37", "EU 38", "EU 39", "EU 40", "EU 41"];
const MEN_SHOE_SIZES = ["EU 40", "EU 41", "EU 42", "EU 43", "EU 44", "EU 45"];
const KIDS_AGES = ["2–3 yrs", "4–5 yrs", "6–7 yrs", "8–9 yrs", "10–12 yrs", "13–14 yrs"];
const COLOURS: TagSuggestion[] = [
  { value: "Black", swatch: "#1c1b17" },
  { value: "White", swatch: "#ffffff" },
  { value: "Cream", swatch: "#f3ead7" },
  { value: "Beige", swatch: "#d9c7a7" },
  { value: "Maroon", swatch: "#6d1a2a" },
  { value: "Red", swatch: "#c0392b" },
  { value: "Pink", swatch: "#e79bb3" },
  { value: "Peach", swatch: "#f4b89a" },
  { value: "Mustard", swatch: "#d4a017" },
  { value: "Green", swatch: "#3f7a4a" },
  { value: "Mint", swatch: "#a8dcc4" },
  { value: "Navy", swatch: "#1f2f5a" },
  { value: "Blue", swatch: "#3b6fd8" },
  { value: "Purple", swatch: "#6b3fa0" },
  { value: "Grey", swatch: "#8a8a8a" },
  { value: "Brown", swatch: "#7a4b2a" },
  { value: "Gold", swatch: "#c9a13b" },
  { value: "Silver", swatch: "#c0c0c0" },
];
const WOMEN_BRANDS = ["Khaadi", "Gul Ahmed", "Sapphire", "Alkaram", "Bonanza Satrangi", "Limelight", "Maria B", "Sana Safinaz", "Nishat Linen", "Beechtree", "Agha Noor", "Asim Jofa"];
const MEN_BRANDS = ["J.", "Bonanza Satrangi", "Edenrobe", "Outfitters", "Breakout", "Charcoal", "Diners", "Cambridge"];
const GLOBAL_BRANDS = ["Zara", "H&M", "Levi's", "Nike", "Adidas", "Mango", "Casio", "Fossil"];
const BUDGETS: { label: string; min: number | null; max: number | null }[] = [
  { label: "Under $25", min: null, max: 25 },
  { label: "$25 – 50", min: 25, max: 50 },
  { label: "$50 – 100", min: 50, max: 100 },
  { label: "$100 – 250", min: 100, max: 250 },
  { label: "$250+", min: 250, max: null },
];

function sizeSuggestions(picked: Set<string>): string[] {
  const any = (...prefixes: string[]) => [...picked].some((id) => prefixes.some((p) => id === p || id.startsWith(`${p}.`)));
  const out: string[] = [];
  if (any("w.eastern", "w.western", "m.eastern", "m.western")) out.push(...CLOTHING_SIZES);
  if (any("w.shoes")) out.push(...WOMEN_SHOE_SIZES);
  if (any("m.shoes")) out.push(...MEN_SHOE_SIZES);
  if (any("k")) out.push(...KIDS_AGES);
  return [...new Set(out)];
}

function brandSuggestions(picked: Set<string>): string[] {
  const out = [...(picked.has("w") ? WOMEN_BRANDS : []), ...(picked.has("m") ? MEN_BRANDS : []), ...GLOBAL_BRANDS];
  return [...new Set(out)];
}

type Index = { nodes: Map<string, TaxonomyNode>; parent: Map<string, string | null> };

function buildIndex(audiences: TaxonomyNode[]): Index {
  const nodes = new Map<string, TaxonomyNode>();
  const parent = new Map<string, string | null>();
  const walk = (list: TaxonomyNode[], p: string | null) => {
    for (const node of list) {
      nodes.set(node.id, node);
      parent.set(node.id, p);
      walk(node.children, node.id);
    }
  };
  walk(audiences, null);
  return { nodes, parent };
}

function descendants(node: TaxonomyNode): string[] {
  return node.children.flatMap((c) => [c.id, ...descendants(c)]);
}

function genderFor(audiences: string[]): Gender | null {
  const has = (id: string) => audiences.includes(id);
  if (has("w") && has("m")) return "unisex";
  if (has("w")) return "women";
  if (has("m")) return "men";
  if (has("k")) return "kids";
  return null;
}

export function PreferencesWizard() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/for-you";
  const qc = useQueryClient();
  const { user, isLoading: sessionLoading } = useSession();

  useEffect(() => {
    if (!sessionLoading && !user) {
      router.replace(`/sign-in?next=${encodeURIComponent(`/preferences?next=${next}`)}`);
    }
  }, [sessionLoading, user, router, next]);

  const taxonomyQuery = useQuery({ queryKey: ["taxonomy"], queryFn: catalog.taxonomy, staleTime: Infinity });
  const prefQuery = useQuery({ queryKey: ["preferences"], queryFn: preferencesApi.get, enabled: !!user });

  const audiences = useMemo(() => taxonomyQuery.data?.audiences ?? [], [taxonomyQuery.data]);
  const index = useMemo(() => buildIndex(audiences), [audiences]);

  const [step, setStep] = useState(0);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [sizes, setSizes] = useState<string[]>([]);
  const [colors, setColors] = useState<string[]>([]);
  const [brands, setBrands] = useState<string[]>([]);
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!prefQuery.data || loaded) return;
    const p = prefQuery.data;
    setPicked(new Set(p.preferred_categories ?? []));
    setSizes(p.preferred_sizes ?? []);
    setColors(p.preferred_colors ?? []);
    setBrands(p.preferred_brands ?? []);
    setBudgetMin(p.budget_min_cents != null ? String(p.budget_min_cents / 100) : "");
    setBudgetMax(p.budget_max_cents != null ? String(p.budget_max_cents / 100) : "");
    setLoaded(true);
  }, [prefQuery.data, loaded]);

  const save = useMutation({
    mutationFn: (payload: Partial<UserPreference>) => preferencesApi.update(payload),
    onSuccess: (data) => qc.setQueryData(["preferences"], data),
  });

  const toggle = (id: string) =>
    setPicked((prev) => {
      const nextSet = new Set(prev);
      const node = index.nodes.get(id);
      if (!node) return prev;
      if (nextSet.has(id)) {
        // un-picking a category also clears everything picked under it
        nextSet.delete(id);
        descendants(node).forEach((d) => nextSet.delete(d));
      } else {
        // picking a style keeps its whole branch picked
        for (let cur: string | null | undefined = id; cur; cur = index.parent.get(cur)) nextSet.add(cur);
      }
      return nextSet;
    });

  const chosenAudiences = audiences.filter((a) => picked.has(a.id));
  const chosenCategories = chosenAudiences.flatMap((a) => a.children.filter((c) => picked.has(c.id)).map((c) => ({ audience: a, category: c })));
  const styleCount = [...picked].filter((id) => (id.match(/\./g)?.length ?? 0) >= 2).length;

  const selection = () => ({
    preferred_categories: [...picked],
    gender: genderFor(chosenAudiences.map((a) => a.id)),
  });

  const goTo = (target: number) => {
    save.mutate(selection());
    setStep(target);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const finish = () => {
    const min = budgetMin.trim() ? Math.round(Number(budgetMin) * 100) : null;
    const max = budgetMax.trim() ? Math.round(Number(budgetMax) * 100) : null;
    save.mutate(
      {
        ...selection(),
        preferred_sizes: sizes,
        preferred_colors: colors,
        preferred_brands: brands,
        budget_min_cents: Number.isFinite(min) ? min : null,
        budget_max_cents: Number.isFinite(max) ? max : null,
      },
      { onSuccess: () => router.push(next) },
    );
  };

  const canContinue = step === 0 ? chosenAudiences.length > 0 : step === 1 ? chosenCategories.length > 0 : true;

  if (sessionLoading || !user || taxonomyQuery.isLoading || (prefQuery.isLoading && !loaded)) {
    return (
      <section className="mx-auto w-[min(880px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  if (taxonomyQuery.isError) {
    return (
      <section className="mx-auto w-[min(880px,calc(100%-42px))] py-24 text-center text-[14px] text-muted">
        Couldn&rsquo;t load categories. Please refresh the page.
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(880px,calc(100%-42px))] pb-10 pt-10 md:pt-14">
      <StepHeader step={step} onJump={(s) => (s < step || canContinue ? goTo(s) : undefined)} maxReachable={picked.size ? 3 : 0} />

      <div key={step} className="tu-page mt-8">
        {step === 0 && (
          <>
            <Title kicker="Step 1 of 4" title={<>Who do you <em>shop for?</em></>} hint="Pick everyone you shop for — you can choose more than one." />
            <div className="tu-stagger mt-7 grid gap-3 sm:grid-cols-3">
              {audiences.map((a) => (
                <BigChoice key={a.id} icon={a.icon} label={a.label} selected={picked.has(a.id)} onClick={() => toggle(a.id)} />
              ))}
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <Title kicker="Step 2 of 4" title={<>What do you <em>love to wear?</em></>} hint="Choose the main categories. You'll narrow them down next." />
            <div className="mt-7 space-y-8">
              {chosenAudiences.map((a) => (
                <div key={a.id}>
                  {chosenAudiences.length > 1 && (
                    <p className="mb-3 text-[12px] font-semibold uppercase tracking-[0.1em] text-faint">
                      {a.icon} {a.label}
                    </p>
                  )}
                  <div className="tu-stagger grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                    {a.children.map((c) => (
                      <CategoryTile
                        key={c.id}
                        node={c}
                        selected={picked.has(c.id)}
                        count={descendants(c).filter((d) => picked.has(d)).length}
                        onClick={() => toggle(c.id)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <Title
              kicker="Step 3 of 4"
              title={<>Narrow it <em>down</em></>}
              hint="Tap the styles you like — more options open as you choose. Leave a category untouched to see everything in it."
            />
            <div className="tu-stagger mt-7 space-y-4">
              {chosenCategories.map(({ audience, category }) => (
                <section key={category.id} className="rounded-[20px] border border-line bg-surface p-5">
                  <h3 className="flex items-center gap-2 text-[15px] font-semibold text-ink">
                    <span aria-hidden="true">{category.icon}</span>
                    {category.label}
                    {chosenAudiences.length > 1 && <span className="text-[12px] font-normal text-faint">· {audience.label}</span>}
                  </h3>
                  {category.children.length === 0 ? (
                    <p className="mt-2 text-[13px] text-muted">We&rsquo;ll show you everything in {category.label.toLowerCase()}.</p>
                  ) : (
                    <div className="mt-3 space-y-3">
                      <ChipRow nodes={category.children} picked={picked} onToggle={toggle} />
                      {category.children
                        .filter((sub) => picked.has(sub.id) && sub.children.length > 0)
                        .map((sub) => (
                          <div key={sub.id} className="tu-pop rounded-[14px] bg-paper-2 p-3">
                            <p className="mb-2 text-[12px] text-muted">
                              Which kind of <b className="text-ink">{sub.label.toLowerCase()}</b>? <span className="text-faint">(optional)</span>
                            </p>
                            <ChipRow nodes={sub.children} picked={picked} onToggle={toggle} small />
                          </div>
                        ))}
                    </div>
                  )}
                </section>
              ))}
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <Title kicker="Step 4 of 4 · optional" title={<>A few <em>details</em></>} hint="Tap what fits you — or type your own. Skip anything you like." />
            <div className="tu-stagger mt-7 space-y-7 rounded-[22px] border border-line bg-surface p-6 sm:p-8">
              <Field label="Your sizes">
                <TagInput values={sizes} onChange={setSizes} suggestions={sizeSuggestions(picked)} placeholder="Type another size and press Enter" />
              </Field>
              <Field label="Colours you love">
                <TagInput values={colors} onChange={setColors} suggestions={COLOURS} placeholder="Type another colour and press Enter" />
              </Field>
              <Field label="Favourite brands">
                <TagInput values={brands} onChange={setBrands} suggestions={brandSuggestions(picked)} placeholder="Type another brand and press Enter" />
              </Field>
              <Field label="Budget per item (USD)">
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {BUDGETS.map((b) => {
                    const on = budgetMin === (b.min?.toString() ?? "") && budgetMax === (b.max?.toString() ?? "");
                    return (
                      <button
                        key={b.label}
                        type="button"
                        aria-pressed={on}
                        onClick={() => {
                          setBudgetMin(on ? "" : (b.min?.toString() ?? ""));
                          setBudgetMax(on ? "" : (b.max?.toString() ?? ""));
                        }}
                        className={`tu-press rounded-full border px-3 py-1.5 text-[12.5px] ${
                          on ? "border-sage bg-sage text-white" : "border-line-strong bg-surface text-ink-soft hover:border-sage hover:text-ink"
                        }`}
                      >
                        {b.label}
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center gap-3">
                  <MoneyInput value={budgetMin} onChange={setBudgetMin} placeholder="Min" />
                  <span className="text-faint">–</span>
                  <MoneyInput value={budgetMax} onChange={setBudgetMax} placeholder="Max" />
                </div>
              </Field>
            </div>
          </>
        )}
      </div>

      {save.isError && (
        <p role="alert" className="mt-4 text-[13px] text-[#a4553f]">
          {save.error instanceof ApiError ? save.error.detail : "Couldn't save your choices — please try again."}
        </p>
      )}

      {/* sticky, not fixed: stays in view while choosing, then scrolls away before the footer */}
      <div className="sticky bottom-0 z-30 mt-8 border-t border-line bg-paper/90 backdrop-blur">
        <div className="flex items-center gap-3 py-3">
          {step > 0 ? (
            <button type="button" onClick={() => goTo(step - 1)} className="tu-press h-11 rounded-full px-4 text-[14px] text-ink-soft hover:text-ink">
              ← Back
            </button>
          ) : (
            <button type="button" onClick={() => router.push(next)} className="tu-press h-11 rounded-full px-4 text-[13px] text-faint hover:text-ink">
              Skip for now
            </button>
          )}
          <span className="ml-auto hidden text-[12.5px] text-muted sm:inline" aria-live="polite">
            {chosenCategories.length > 0 &&
              `${chosenCategories.length} ${chosenCategories.length === 1 ? "category" : "categories"}${styleCount ? ` · ${styleCount} ${styleCount === 1 ? "style" : "styles"}` : ""}`}
          </span>
          {step < 3 ? (
            <Button size="md" className="ml-auto sm:ml-0" disabled={!canContinue} onClick={() => goTo(step + 1)}>
              Continue <span aria-hidden="true">→</span>
            </Button>
          ) : (
            <Button size="md" className="ml-auto sm:ml-0" disabled={save.isPending} onClick={finish}>
              {save.isPending ? "Saving…" : "See my picks"} <span aria-hidden="true">→</span>
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}

function StepHeader({ step, onJump, maxReachable }: { step: number; onJump: (s: number) => void; maxReachable: number }) {
  return (
    <ol className="flex items-center gap-2 sm:gap-3" aria-label="Progress">
      {STEPS.map((label, i) => {
        const done = i < step;
        const active = i === step;
        const reachable = i <= Math.max(step, maxReachable);
        return (
          <li key={label} className="flex flex-1 items-center gap-2 sm:gap-3">
            <button
              type="button"
              disabled={!reachable || active}
              onClick={() => onJump(i)}
              aria-current={active ? "step" : undefined}
              className="tu-tap flex items-center gap-2 disabled:cursor-default"
            >
              <span
                className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[12px] font-semibold transition-colors duration-300 ${
                  done ? "border-sage bg-sage text-white" : active ? "border-sage text-sage-deep" : "border-line-strong text-faint"
                }`}
              >
                {done ? "✓" : i + 1}
              </span>
              <span className={`hidden text-[13px] sm:inline ${active || done ? "text-ink" : "text-faint"}`}>{label}</span>
            </button>
            {i < STEPS.length - 1 && (
              <span className="relative h-px flex-1 overflow-hidden bg-line">
                <span
                  className={`absolute inset-0 origin-left bg-sage transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                    done ? "scale-x-100" : "scale-x-0"
                  }`}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Title({ kicker, title, hint }: { kicker: string; title: ReactNode; hint: string }) {
  return (
    <div>
      <p className="text-[11.5px] font-semibold uppercase tracking-[0.12em] text-sage-deep">{kicker}</p>
      <h1 className="mt-2 font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">{title}</h1>
      <p className="mt-2 max-w-xl text-[14.5px] leading-relaxed text-muted">{hint}</p>
    </div>
  );
}

function BigChoice({ icon, label, selected, onClick }: { icon: string; label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`tu-press relative flex items-center gap-4 rounded-[22px] border p-5 text-left sm:flex-col sm:items-start sm:p-6 ${
        selected ? "border-sage bg-sage-tint/40 ring-2 ring-sage/30" : "border-line bg-surface hover:border-line-strong"
      }`}
    >
      <span className="text-[34px] leading-none" aria-hidden="true">{icon}</span>
      <span className="font-display text-[20px] text-ink">{label}</span>
      <Check selected={selected} />
    </button>
  );
}

function CategoryTile({
  node,
  selected,
  count,
  onClick,
}: {
  node: TaxonomyNode;
  selected: boolean;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`tu-press relative flex min-h-[104px] flex-col justify-between rounded-[18px] border p-4 text-left ${
        selected ? "border-sage bg-sage-tint/40 ring-2 ring-sage/30" : "border-line bg-surface hover:border-line-strong"
      }`}
    >
      <span className="text-[26px] leading-none" aria-hidden="true">{node.icon}</span>
      <span>
        <span className="block text-[14px] font-medium text-ink">{node.label}</span>
        <span className="block text-[11.5px] text-faint">
          {selected && count > 0 ? `${count} picked` : `${node.children.length} types`}
        </span>
      </span>
      <Check selected={selected} />
    </button>
  );
}

function Check({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`absolute right-3 top-3 grid h-6 w-6 place-items-center rounded-full bg-sage text-[12px] text-white transition-[transform,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
        selected ? "scale-100 opacity-100" : "scale-50 opacity-0"
      }`}
    >
      ✓
    </span>
  );
}

function ChipRow({
  nodes,
  picked,
  onToggle,
  small,
}: {
  nodes: TaxonomyNode[];
  picked: Set<string>;
  onToggle: (id: string) => void;
  small?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {nodes.map((node) => {
        const on = picked.has(node.id);
        return (
          <button
            key={node.id}
            type="button"
            aria-pressed={on}
            onClick={() => onToggle(node.id)}
            className={`tu-press inline-flex items-center gap-1.5 rounded-full border ${small ? "px-3 py-1.5 text-[12.5px]" : "px-3.5 py-2 text-[13.5px]"} ${
              on ? "border-sage bg-sage text-white" : "border-line-strong bg-surface text-ink-soft hover:border-sage hover:text-ink"
            }`}
          >
            {on && <span aria-hidden="true">✓</span>}
            {node.label}
            {!small && node.children.length > 0 && !on && <span className="text-faint" aria-hidden="true">+</span>}
          </button>
        );
      })}
    </div>
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

function MoneyInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative flex-1">
      <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[14px] text-faint">$</span>
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={`${placeholder} budget`}
        className="h-11 w-full rounded-xl border border-line-strong bg-paper pl-7 pr-3.5 text-[14px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
      />
    </div>
  );
}
