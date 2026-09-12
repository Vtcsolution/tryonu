"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { affiliateGoUrl, resolveMediaUrl } from "@/lib/api/client";
import { savedLooks as savedLooksApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { SavedLook } from "@/lib/api/types";

export function SavedLooksGallery() {
  const router = useRouter();
  const { user, isLoading: sessionLoading } = useSession();

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/saved");
  }, [sessionLoading, user, router]);

  const looksQuery = useQuery({
    queryKey: ["saved-looks"],
    queryFn: savedLooksApi.list,
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
      <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
        Your <em>saved looks</em>
      </h1>
      <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
        Try-on results you've kept — revisit them or shop the original product.
      </p>

      <div className="mt-8">
        {looksQuery.isLoading && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] animate-pulse rounded-[20px] bg-paper-2" />
            ))}
          </div>
        )}

        {looksQuery.data && looksQuery.data.length === 0 && (
          <div className="rounded-[22px] border border-dashed border-line p-10 text-center">
            <p className="text-[14px] text-muted">
              No saved looks yet — try something on and save it from the result screen.
            </p>
            <Button href="/try" size="md" className="mt-5">
              Start a try-on <span aria-hidden="true">→</span>
            </Button>
          </div>
        )}

        {looksQuery.data && looksQuery.data.length > 0 && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {looksQuery.data.map((look) => (
              <SavedLookCard key={look.id} look={look} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function SavedLookCard({ look }: { look: SavedLook }) {
  const qc = useQueryClient();
  const remove = useMutation({
    mutationFn: () => savedLooksApi.remove(look.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-looks"] }),
  });

  const image = resolveMediaUrl(look.image_url);

  return (
    <div className="group overflow-hidden rounded-[20px] border border-line bg-surface">
      <div className="relative aspect-[3/4] bg-paper-2">
        {image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt={look.title ?? "Saved look"} className="h-full w-full object-cover object-top" />
        )}
        <button
          type="button"
          onClick={() => remove.mutate()}
          disabled={remove.isPending}
          aria-label="Remove saved look"
          className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-full bg-white/90 text-[13px] text-[#1c1b17] opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 disabled:opacity-60"
        >
          ✕
        </button>
      </div>
      <div className="p-3">
        {look.product ? (
          <>
            <p className="truncate text-[13px] font-semibold text-ink">{look.product.name}</p>
            <p className="mt-0.5 text-[12px] text-muted">
              {(look.product.price_cents / 100).toFixed(2)} {look.product.currency.toUpperCase()} ·{" "}
              {look.product.merchant_name
                ? `${look.product.retailer.name} · ${look.product.merchant_name}`
                : look.product.retailer.name}
            </p>
            <Button href={affiliateGoUrl(look.product.id, "saved_look")} size="sm" className="mt-3 w-full">
              Shop now
            </Button>
          </>
        ) : (
          <p className="text-[12px] text-muted">{look.title ?? "Saved look"}</p>
        )}
      </div>
    </div>
  );
}
