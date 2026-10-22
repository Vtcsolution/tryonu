"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { mySize, type MySize, type SizeSuggestion } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const KEY = ["my-size"];

type Form = { gender: "women" | "men"; height: string; weight: string; bust: string; waist: string; hips: string; shoe: string; fit: "regular" | "loose" | "slim" };

const num = (v: string) => {
  const n = Number(v.replace(",", "."));
  return v.trim() && Number.isFinite(n) && n > 0 ? Math.round(n) : null;
};

/** One line: "M · UK 12 · US 8 · EU 40", or the men's equivalents. */
export function sizeLine(s: SizeSuggestion): string {
  const parts = [s.letter];
  if (s.audience === "women") parts.push(`UK ${s.uk}`, `US ${s.us}`, `EU ${s.eu}`);
  else parts.push(`chest ${s.chest_in}″`, `EU ${s.eu}`, `trousers waist ${s.trousers_waist_in}″`);
  return parts.filter((p) => p && !p.includes("null")).join(" · ");
}

/** The "My size" card on the preferences page: measurements in, the size to pick out. */
export function MySizeCard() {
  const qc = useQueryClient();
  const { user } = useSession();
  const saved = useQuery({ queryKey: KEY, queryFn: mySize.get, enabled: !!user });
  const [f, setF] = useState<Form | null>(null);
  const [unit, setUnit] = useState<"metric" | "imperial">("metric");
  useEffect(() => {
    if (saved.data && !f) {
      const d = saved.data;
      setF({
        gender: d.gender ?? "women",
        height: d.height_cm?.toString() ?? "",
        weight: d.weight_kg?.toString() ?? "",
        bust: d.bust_cm?.toString() ?? "",
        waist: d.waist_cm?.toString() ?? "",
        hips: d.hips_cm?.toString() ?? "",
        shoe: d.shoe_eu?.toString() ?? "",
        fit: d.fit ?? "regular",
      });
    }
  }, [saved.data, f]);
  const save = useMutation({
    mutationFn: (form: Form) => {
      // centimetres and kilograms on our side; feet/inches and pounds converted here
      const cm = (v: string) => (unit === "imperial" && num(v) ? Math.round(num(v)! * 2.54) : num(v));
      return mySize.save({
        gender: form.gender,
        height_cm: cm(form.height),
        weight_kg: unit === "imperial" && num(form.weight) ? Math.round(num(form.weight)! * 0.4536) : num(form.weight),
        bust_cm: cm(form.bust),
        waist_cm: cm(form.waist),
        hips_cm: cm(form.hips),
        shoe_eu: num(form.shoe),
        fit: form.fit,
      });
    },
    onSuccess: (d: MySize) => qc.setQueryData(KEY, d),
  });
  if (!user || !f) return null;
  const set = (patch: Partial<Form>) => setF({ ...f, ...patch });
  const s = saved.data?.suggestion;
  const field = "mt-1 block h-11 w-full rounded-xl border border-line-strong bg-paper px-3 text-[15px] text-ink outline-none focus:border-sage";
  const lengthUnit = unit === "metric" ? "cm" : "inches";
  return (
    <section id="size" className="tu-container scroll-mt-24 pb-14">
      <div className="mx-auto max-w-3xl rounded-[24px] border border-line bg-surface p-5 md:p-7">
        <h2 className="font-display text-[28px] leading-tight text-ink">My size</h2>
        <p className="mt-1 text-[15.5px] text-muted">
          Add your height and weight once, and we&apos;ll show your size next to products. More measurements = a better fit.
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          {(["women", "men"] as const).map((g) => (
            <button key={g} type="button" onClick={() => set({ gender: g })} aria-pressed={f.gender === g}
              className={`min-h-[42px] rounded-full border px-4 text-[14.5px] font-semibold ${f.gender === g ? "border-sage bg-sage text-white" : "border-line-strong text-ink"}`}>
              {g === "women" ? "Women's sizes" : "Men's sizes"}
            </button>
          ))}
          <span className="flex-1" />
          <div className="flex rounded-full border border-line p-1" role="group" aria-label="Units">
            {(["metric", "imperial"] as const).map((u) => (
              <button key={u} type="button" onClick={() => setUnit(u)} aria-pressed={unit === u}
                className={`min-h-[34px] rounded-full px-3 text-[13.5px] font-semibold ${unit === u ? "bg-ink text-surface" : "text-ink-soft"}`}>
                {u === "metric" ? "cm / kg" : "inches / lb"}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <label className="text-[13.5px] font-semibold text-ink">Height ({lengthUnit})
            <input inputMode="decimal" value={f.height} onChange={(e) => set({ height: e.target.value })} placeholder={unit === "metric" ? "e.g. 165" : "e.g. 65"} className={field} />
          </label>
          <label className="text-[13.5px] font-semibold text-ink">Weight ({unit === "metric" ? "kg" : "lb"})
            <input inputMode="decimal" value={f.weight} onChange={(e) => set({ weight: e.target.value })} placeholder={unit === "metric" ? "e.g. 60" : "e.g. 132"} className={field} />
          </label>
          <label className="text-[13.5px] font-semibold text-ink">Shoe size (EU)
            <input inputMode="numeric" value={f.shoe} onChange={(e) => set({ shoe: e.target.value })} placeholder="e.g. 38" className={field} />
          </label>
          <label className="text-[13.5px] font-semibold text-ink">{f.gender === "men" ? "Chest" : "Bust"} ({lengthUnit}, optional)
            <input inputMode="decimal" value={f.bust} onChange={(e) => set({ bust: e.target.value })} className={field} />
          </label>
          <label className="text-[13.5px] font-semibold text-ink">Waist ({lengthUnit}, optional)
            <input inputMode="decimal" value={f.waist} onChange={(e) => set({ waist: e.target.value })} className={field} />
          </label>
          <label className="text-[13.5px] font-semibold text-ink">Hips ({lengthUnit}, optional)
            <input inputMode="decimal" value={f.hips} onChange={(e) => set({ hips: e.target.value })} className={field} />
          </label>
        </div>

        <div className="mt-4">
          <p className="text-[13.5px] font-semibold text-ink">How do you like clothes to fit?</p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {([["slim", "Close-fitting"], ["regular", "Regular"], ["loose", "Loose and easy"]] as const).map(([id, label]) => (
              <button key={id} type="button" onClick={() => set({ fit: id })} aria-pressed={f.fit === id}
                className={`min-h-[40px] rounded-full border px-4 text-[14px] font-semibold ${f.fit === id ? "border-sage bg-sage-tint/50 text-sage-deep" : "border-line-strong text-ink"}`}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => save.mutate(f)} disabled={save.isPending}
            className="tu-press min-h-[48px] rounded-full bg-sage px-6 text-[15.5px] font-semibold text-white disabled:opacity-60">
            {save.isPending ? "Saving…" : "Save and show my size"}
          </button>
          {save.isError && <span className="text-[14px] text-[#a4553f]">{save.error instanceof ApiError ? "Please check the numbers." : "Couldn't save."}</span>}
        </div>

        {s && (
          <div className="mt-5 rounded-[18px] border border-sage/40 bg-sage-tint/25 p-4">
            {s.letter && (
              <>
                <p className="text-[13px] font-semibold uppercase tracking-[0.1em] text-sage-deep">Your clothes size</p>
                <p className="mt-1 font-display text-[30px] leading-none text-ink">{s.letter}</p>
                <p className="mt-1.5 text-[15px] text-ink-soft">{sizeLine(s).split(" · ").slice(1).join(" · ")}</p>
              </>
            )}
            {s.shoe && (
              <p className="mt-2 text-[15px] text-ink">
                <b>Shoes:</b> EU {s.shoe.eu} · UK {s.shoe.uk} · US {s.shoe.us}
              </p>
            )}
            <p className="mt-2 text-[13px] text-muted">
              {s.basis === "height_weight" ? "Worked out from your height and weight: add your measurements for a closer answer. " : ""}
              Shops cut differently, so always check the shop&apos;s own size chart before you buy.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

/** Next to a product: "Your size: M · UK 12 · …" (or a link to work it out). */
export function YourSize({ name }: { name: string }) {
  const { user } = useSession();
  const q = useQuery({ queryKey: KEY, queryFn: mySize.get, enabled: !!user, staleTime: 5 * 60_000 });
  if (!user || q.isLoading) return null;
  const lower = name.toLowerCase();
  // jewellery, bags, watches, glasses and the like have no size
  if (/\b(earring|necklace|bangle|bracelet|ring|jhumka|tikka|watch|bag|clutch|purse|wallet|sunglass|glasses|perfume|scarf|dupatta)s?\b/.test(lower)) return null;
  const shoes = /\b(shoe|sneaker|trainer|boot|sandal|heel|pump|loafer|slipper|khussa|kolhapuri|flat)s?\b/.test(lower);
  const s = q.data?.suggestion;
  if (!s || (shoes ? !s.shoe : !s.letter)) {
    return (
      <Link href="/preferences#size" className="mt-2 inline-flex text-[14px] font-semibold text-sage-deep hover:underline">
        Not sure of your size? Find it in a minute →
      </Link>
    );
  }
  return (
    <p className="mt-2 rounded-xl bg-sage-tint/30 px-3 py-2 text-[14px] text-ink">
      <b>Your size:</b> {shoes && s.shoe ? `EU ${s.shoe.eu} · UK ${s.shoe.uk} · US ${s.shoe.us}` : sizeLine(s)}
      <span className="block text-[12.5px] text-muted">Check the shop&apos;s size chart too: sizes vary by shop.</span>
    </p>
  );
}
