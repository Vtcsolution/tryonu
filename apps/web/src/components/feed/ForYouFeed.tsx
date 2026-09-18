"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError, affiliateGoUrl, thumbnailUrl } from "@/lib/api/client";
import { feed as feedApi, products as productsApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { ForYouFeed as FeedData } from "@/lib/api/types";

type Item = FeedData["items"][number];

export function ForYouFeed() {
  const router = useRouter();
  const { user, isLoading: sessionLoading } = useSession();
  const [node, setNode] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/for-you");
  }, [sessionLoading, user, router]);

  const query = useQuery({
    queryKey: ["for-you", node ?? "mix"],
    queryFn: () => feedApi.forYou(node),
    enabled: !!user,
    placeholderData: keepPreviousData,
  });

  // A feed card is a live retailer result; it only becomes a saved product
  // (needed for try-on and tracked shop links) once the user acts on it.
  const select = useMutation({
    mutationFn: (item: Item) =>
      productsApi.selectLive({
        query: item.search_term ?? item.name,
        retailer_slug: item.retailer_slug,
        retailer_product_id: item.retailer_product_id,
      }),
  });

  const tryOn = (item: Item) =>
    select.mutate(item, { onSuccess: (product) => router.push(`/try?product=${product.id}`) });

  const shop = (item: Item) => {
    // opened synchronously so popup blockers allow it, pointed at the
    // tracked link once the product is saved
    const tab = window.open("", "_blank");
    select.mutate(item, {
      onSuccess: (product) => {
        const url = affiliateGoUrl(product.id, "product_card");
        if (tab) {
          tab.opener = null;
          tab.location.href = url;
        } else {
          window.location.href = url;
        }
      },
      onError: () => tab?.close(),
    });
  };

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  const data = query.data;
  const noPicks = data && data.sections.length === 0;

  return (
    <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-10 md:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11.5px] font-semibold uppercase tracking-[0.12em] text-sage-deep">For you</p>
          <h1 className="mt-1 font-display text-[clamp(28px,4.4vw,44px)] leading-tight text-ink">
            Picked for <em>your style</em>
          </h1>
          <p className="mt-2 max-w-xl text-[14.5px] text-muted">
            Live from real stores, based on what you told us you love. Try anything on yourself before you buy.
          </p>
        </div>
        <Button href="/preferences?next=%2Ffor-you" variant="outline" size="sm">
          Edit my picks
        </Button>
      </div>

      {query.isLoading ? (
        <FeedSkeleton />
      ) : query.isError ? (
        <div className="mt-10 rounded-[22px] border border-line bg-surface p-8 text-center">
          <p className="text-[14px] text-muted">
            {query.error instanceof ApiError ? query.error.detail : "Couldn't load your picks right now."}
          </p>
          <Button size="sm" variant="outline" className="mt-4" onClick={() => query.refetch()}>
            Try again
          </Button>
        </div>
      ) : noPicks ? (
        <div className="tu-pop mt-10 rounded-[26px] border border-line bg-surface px-6 py-12 text-center">
          <p className="text-[38px]" aria-hidden="true">🧭</p>
          <p className="mt-3 font-display text-[24px] text-ink">Tell us what you love</p>
          <p className="mx-auto mt-2 max-w-md text-[14px] text-muted">
            Pick your categories — shalwar kameez, bangles, shoes, anything — and we&rsquo;ll fill this page with matching products.
          </p>
          <Button href="/preferences?next=%2Ffor-you" size="md" className="mt-6">
            Choose my categories <span aria-hidden="true">→</span>
          </Button>
        </div>
      ) : (
        data && (
          <>
            <div className="-mx-1 mt-7 flex gap-2 overflow-x-auto px-1 pb-2" role="tablist" aria-label="Your categories">
              <Chip label="Top picks" active={!node} onClick={() => setNode(undefined)} />
              {data.sections.map((s) => (
                <Chip
                  key={s.id}
                  label={s.parent_label ? `${s.label} · ${s.parent_label}` : s.label}
                  active={node === s.id}
                  onClick={() => setNode(s.id)}
                />
              ))}
            </div>

            {select.isError && (
              <p role="alert" className="mt-3 text-[13px] text-[#a4553f]">
                {select.error instanceof ApiError ? select.error.detail : "That item isn't available any more — try another."}
              </p>
            )}

            {data.items.length === 0 ? (
              <div className="mt-6 rounded-[22px] border border-dashed border-line p-10 text-center text-[14px] text-muted">
                No matches in this category right now — try another one or widen your budget.
              </div>
            ) : (
              <div
                key={node ?? "mix"}
                className={`tu-stagger mt-6 grid grid-cols-2 gap-4 transition-opacity sm:grid-cols-3 lg:grid-cols-4 ${
                  query.isFetching && query.isPlaceholderData ? "opacity-50" : ""
                }`}
              >
                {data.items.map((item) => (
                  <ProductCard
                    key={`${item.retailer_slug}:${item.retailer_product_id}`}
                    item={item}
                    busy={select.isPending && select.variables?.retailer_product_id === item.retailer_product_id}
                    disabled={select.isPending}
                    onTry={() => tryOn(item)}
                    onShop={() => shop(item)}
                  />
                ))}
              </div>
            )}
          </>
        )
      )}
    </section>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`tu-press shrink-0 whitespace-nowrap rounded-full px-4 py-2 text-[13px] ${
        active ? "bg-ink text-paper" : "border border-line bg-surface text-ink-soft hover:border-line-strong hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

function ProductCard({
  item,
  busy,
  disabled,
  onTry,
  onShop,
}: {
  item: Item;
  busy: boolean;
  disabled: boolean;
  onTry: () => void;
  onShop: () => void;
}) {
  const image = thumbnailUrl(item.images[0]);
  return (
    <article className="group tu-hover-card flex flex-col overflow-hidden rounded-[20px] border border-line bg-surface">
      <div className="relative aspect-[3/4] overflow-hidden bg-paper-2">
        {image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt={item.name} loading="lazy" className="tu-hover-media h-full w-full object-cover object-top" />
        )}
        <span className="absolute left-2 top-2 rounded-md bg-surface/95 px-2 py-1 text-[10px] font-semibold text-ink">
          {item.retailer_name}
        </span>
        {busy && (
          <span className="absolute inset-0 grid place-items-center bg-surface/60">
            <span className="h-7 w-7 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col p-3">
        <p className="line-clamp-2 text-[13px] font-medium leading-snug text-ink">{item.name}</p>
        <p className="mt-1 text-[13px] text-ink-soft">
          {(item.price_cents / 100).toFixed(2)} {item.currency.toUpperCase()}
        </p>
        <div className="mt-auto grid grid-cols-2 gap-2 pt-3">
          <button
            type="button"
            disabled={disabled}
            onClick={onTry}
            className="tu-press h-9 rounded-full bg-sage text-[12.5px] font-medium text-white hover:bg-sage-deep disabled:opacity-50"
          >
            Try on
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={onShop}
            className="tu-press h-9 rounded-full border border-line-strong text-[12.5px] font-medium text-ink hover:border-ink/40 disabled:opacity-50"
          >
            Shop
          </button>
        </div>
      </div>
    </article>
  );
}

function FeedSkeleton() {
  return (
    <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="animate-pulse overflow-hidden rounded-[20px] border border-line">
          <div className="aspect-[3/4] bg-paper-2" />
          <div className="space-y-2 p-3">
            <div className="h-3 w-3/4 rounded bg-paper-2" />
            <div className="h-3 w-1/3 rounded bg-paper-2" />
          </div>
        </div>
      ))}
    </div>
  );
}
