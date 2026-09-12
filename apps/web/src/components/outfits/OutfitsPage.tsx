"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { affiliateGoUrl, resolveMediaUrl } from "@/lib/api/client";
import { outfits as outfitsApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import { OutfitBuilder } from "@/components/outfits/OutfitBuilder";
import type { Outfit } from "@/lib/api/types";

export function OutfitsPage() {
  const router = useRouter();
  const { user, isLoading: sessionLoading } = useSession();
  const [building, setBuilding] = useState(false);

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/outfits");
  }, [sessionLoading, user, router]);

  const outfitsQuery = useQuery({
    queryKey: ["outfits"],
    queryFn: outfitsApi.list,
    enabled: !!user,
  });

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-14 md:py-20">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
            Outfit <em>builder</em>
          </h1>
          <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
            Combine real products into a complete outfit — see a live compatibility score as you build.
          </p>
        </div>
        <Button size="md" onClick={() => setBuilding((v) => !v)}>
          {building ? "Cancel" : "+ Build outfit"}
        </Button>
      </div>

      {building && (
        <div className="mt-8">
          <OutfitBuilder
            onSaved={() => {
              setBuilding(false);
              outfitsQuery.refetch();
            }}
          />
        </div>
      )}

      <div className="mt-10">
        {outfitsQuery.isLoading && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-64 animate-pulse rounded-[20px] bg-paper-2" />
            ))}
          </div>
        )}

        {outfitsQuery.data && outfitsQuery.data.length === 0 && !building && (
          <div className="rounded-[22px] border border-dashed border-line p-10 text-center">
            <p className="text-[14px] text-muted">No outfits yet — build one from real products.</p>
          </div>
        )}

        {outfitsQuery.data && outfitsQuery.data.length > 0 && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {outfitsQuery.data.map((outfit) => (
              <OutfitCard key={outfit.id} outfit={outfit} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function OutfitCard({ outfit }: { outfit: Outfit }) {
  const qc = useQueryClient();
  const remove = useMutation({
    mutationFn: () => outfitsApi.remove(outfit.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["outfits"] }),
  });

  const score = outfit.compatibility_score;
  const scoreTone = score == null ? "" : score >= 65 ? "text-sage-deep" : "text-[#a4553f]";

  return (
    <div className="overflow-hidden rounded-[22px] border border-line bg-surface">
      <div className="flex gap-1 p-3">
        {outfit.items.slice(0, 4).map((item) => {
          const thumb = resolveMediaUrl(item.product.images[0]?.url);
          return (
            <div key={item.id} className="aspect-[3/4] flex-1 overflow-hidden rounded-[12px] bg-paper-2">
              {thumb && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={thumb} alt={item.product.name} className="h-full w-full object-cover object-top" />
              )}
            </div>
          );
        })}
      </div>
      <div className="border-t border-line p-4">
        <div className="flex items-center justify-between">
          <p className="font-display text-[16px] text-ink">{outfit.name || outfit.occasion || "Outfit"}</p>
          {score != null && (
            <span className={`text-[13px] font-semibold ${scoreTone}`}>{score}% match</span>
          )}
        </div>
        <p className="mt-1 text-[13px] text-muted">
          {outfit.items.length} items · {(outfit.total_price_cents / 100).toFixed(2)}
        </p>
        {outfit.compatibility_notes && outfit.compatibility_notes.length > 0 && (
          <ul className="mt-2 space-y-1 text-[12px] text-faint">
            {outfit.compatibility_notes.map((n) => (
              <li key={n}>· {n}</li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {outfit.items.map((item) => (
            <Button
              key={item.id}
              href={affiliateGoUrl(item.product.id, "outfit")}
              size="sm"
              variant="outline"
              className="!h-8 !px-3 !text-[11.5px]"
            >
              Shop {item.product.name.length > 18 ? `${item.product.name.slice(0, 18)}…` : item.product.name}
            </Button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => remove.mutate()}
          disabled={remove.isPending}
          className="mt-3 text-[12.5px] text-faint transition-colors hover:text-[#a4553f]"
        >
          {remove.isPending ? "Removing…" : "Remove outfit"}
        </button>
      </div>
    </div>
  );
}
