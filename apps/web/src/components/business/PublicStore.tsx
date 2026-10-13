"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ProductCard } from "@/components/product/ProductCard";
import { ApiError, affiliateGoUrl } from "@/lib/api/client";
import { stores as storesApi } from "@/lib/api/endpoints";
import type { StoreProduct } from "@/lib/api/types";
import { countryName } from "@/lib/countries";

/** A company's own page on TryOnU: its details and every product it sells. */
export function PublicStore({ slug }: { slug: string }) {
  const router = useRouter();
  const store = useQuery({ queryKey: ["public-store", slug], queryFn: () => storesApi.publicStore(slug), retry: false });
  const tryOn = useMutation({
    mutationFn: (p: StoreProduct) => storesApi.selectProduct(slug, p.id),
    onSuccess: ({ product_id }) => router.push(`/try?product=${product_id}`),
  });
  const buy = useMutation({ mutationFn: (p: StoreProduct) => storesApi.selectProduct(slug, p.id) });
  const onBuy = (p: StoreProduct) => {
    // opened now so popup blockers allow it, then pointed at the tracked shop link
    const tab = window.open("", "_blank");
    buy.mutate(p, {
      onSuccess: ({ product_id }) => {
        const url = affiliateGoUrl(product_id, "product_card");
        if (tab) {
          tab.opener = null;
          tab.location.href = url;
        } else window.location.href = url;
      },
      onError: () => tab?.close(),
    });
  };

  if (store.isLoading) {
    return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  }
  if (store.isError || !store.data) {
    const missing = store.error instanceof ApiError && store.error.status === 404;
    return (
      <section className="mx-auto w-[min(720px,calc(100%-32px))] py-24 text-center">
        <h1 className="font-display text-[28px] text-ink">{missing ? "Store not found" : "Couldn't load this store"}</h1>
        <p className="mt-3 text-[15px] text-muted">{missing ? "This store isn't open on TryOnU right now." : "Please try again in a moment."}</p>
      </section>
    );
  }
  const s = store.data;
  const busyId = tryOn.isPending ? tryOn.variables?.id : buy.isPending ? buy.variables?.id : undefined;

  return (
    <section className="mx-auto w-[min(1180px,calc(100%-32px))] py-12 md:py-16">
      <header className="flex flex-wrap items-center gap-5 rounded-[28px] border border-line bg-surface p-6 md:p-8">
        {s.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={s.logo_url} alt="" className="h-20 w-20 rounded-[20px] border border-line object-cover" />
        ) : (
          <div className="grid h-20 w-20 place-items-center rounded-[20px] bg-sage font-display text-[32px] text-white">
            {s.name.slice(0, 1).toUpperCase()}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Store on TryOnU · {countryName(s.country)}</p>
          <h1 className="mt-1 font-display text-[clamp(28px,4vw,40px)] leading-tight text-ink">{s.name}</h1>
          {s.description && <p className="mt-2 max-w-2xl text-[14.5px] leading-relaxed text-muted">{s.description}</p>}
        </div>
        {s.website_url && (
          <a
            href={s.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="tu-press rounded-full border border-line-strong px-4 py-2 text-[13px] font-medium text-ink hover:border-ink/40"
          >
            Visit website ↗
          </a>
        )}
      </header>

      <p className="mt-8 text-[13px] text-muted">
        {s.products.length} product{s.products.length === 1 ? "" : "s"} · try any of them on your own photo before you buy
      </p>
      {(tryOn.isError || buy.isError) && (
        <p role="alert" className="mt-3 text-[13px] text-[#a4553f]">
          {(tryOn.error ?? buy.error) instanceof ApiError ? ((tryOn.error ?? buy.error) as ApiError).detail : "That product isn't available right now."}
        </p>
      )}
      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {s.products.map((p) => (
          <ProductCard
            key={p.id}
            image={p.images[0]}
            name={p.name}
            priceCents={p.price_cents}
            currency={p.currency}
            shop={s.name}
            label={p.category}
            busy={busyId === p.id}
            primary={{ label: "Try it on", onClick: () => tryOn.mutate(p), disabled: busyId !== undefined }}
            secondary={{ label: "Buy ↗", onClick: () => onBuy(p), disabled: busyId !== undefined }}
          />
        ))}
      </div>
    </section>
  );
}
