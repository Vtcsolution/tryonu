"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { formatPrice } from "@/components/try/shop";
import { readyLooks, type ReadyLook } from "@/lib/api/endpoints";
import { LookCanvas } from "./LookCanvas";
import { TryLookButton } from "./TryLookButton";

const FILTERS: [string, string][] = [
  ["", "All"],
  ["women", "Women"],
  ["men", "Men"],
  ["kids", "Kids"],
];

/** The Ready looks, with Women / Men / Kids filters. The first page comes from
 * the server (instant, and readable by search engines); filters load on tap. */
export function LooksGrid({ initial, limit }: { initial: ReadyLook[]; limit?: number }) {
  const [audience, setAudience] = useState("");
  const looks = useQuery({
    queryKey: ["ready-looks", audience],
    queryFn: () => readyLooks.list(audience || undefined),
    initialData: audience === "" ? initial : undefined,
    staleTime: 5 * 60_000,
  });
  const shown = (looks.data ?? []).slice(0, limit ?? 96);

  return (
    <div>
      {!limit && (
        <div role="tablist" aria-label="Who the look is for" className="mb-6 flex w-fit rounded-full border border-line bg-surface p-1">
          {FILTERS.map(([id, label]) => (
            <button
              key={id || "all"}
              type="button"
              role="tab"
              aria-selected={audience === id}
              onClick={() => setAudience(id)}
              className={`min-h-[42px] rounded-full px-5 text-[15px] font-semibold transition-colors ${
                audience === id ? "bg-sage text-white" : "text-ink-soft hover:text-ink"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {looks.isFetching && !looks.data ? (
        <div className="grid grid-cols-1 gap-5 min-[480px]:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="aspect-[4/5] animate-pulse rounded-[24px] bg-paper-2" />
          ))}
        </div>
      ) : shown.length === 0 ? (
        <p className="rounded-[20px] border border-dashed border-line p-8 text-center text-[16px] text-muted">
          New looks are on the way. Check back soon.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-6 min-[480px]:grid-cols-2 lg:grid-cols-3">
          {shown.map((look, i) => (
            <article key={look.id} className="flex flex-col overflow-hidden rounded-[24px] border border-line bg-surface">
              <div className="relative">
                <LookCanvas look={look} href={`/looks/${look.id}`} priority={i < 3} />
              </div>
              <Link href={`/looks/${look.id}`} className="group block">
                <div className="px-4 pt-4">
                  <h2 className="text-[18px] font-semibold leading-snug text-ink group-hover:text-sage-deep">
                    {look.title}
                    {look.season && <span className="ml-2 rounded-full bg-paper-2 px-2 py-0.5 align-middle text-[12px] font-semibold text-ink-soft">{look.season}</span>}
                  </h2>
                  <p className="mt-0.5 text-[14.5px] text-muted">
                    {look.items.length} {look.items.length === 1 ? "product" : "products"}
                    {look.total_cents != null && look.currency ? ` · ${formatPrice(look.total_cents, look.currency)} in total` : ""}
                  </p>
                </div>
              </Link>
              <div className="mt-auto p-4">
                <TryLookButton lookId={look.id} size="md" className="w-full" />
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
