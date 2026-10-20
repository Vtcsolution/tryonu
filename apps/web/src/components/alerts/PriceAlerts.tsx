"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { formatPrice } from "@/components/try/shop";
import { Button } from "@/components/ui/Button";
import { affiliateGoUrl, relayedImageUrl } from "@/lib/api/client";
import { priceAlerts } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const IDS_KEY = ["price-alerts", "ids"];

export function BellPlusIcon({ size = 18, on = false }: { size?: number; on?: boolean }) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 9.5a6 6 0 0 1 12 0c0 4.6 1.8 6.2 2.5 7H3.5c.7-.8 2.5-2.4 2.5-7z" />
      <path d="M10 19.5a2.2 2.2 0 0 0 4 0" fill="none" />
    </svg>
  );
}

/** "Price alert": tell me when this gets cheaper or is back in stock. */
export function PriceAlertButton({ productId, size = "wide" }: { productId: string; size?: "wide" | "small" }) {
  const qc = useQueryClient();
  const { user } = useSession();
  const ids = useQuery({ queryKey: IDS_KEY, queryFn: priceAlerts.ids, enabled: !!user });
  const on = ids.data?.includes(productId) ?? false;
  const toggle = useMutation({
    mutationFn: async (): Promise<void> => {
      if (on) await priceAlerts.remove(productId);
      else await priceAlerts.add(productId);
    },
    onMutate: () => qc.setQueryData<string[]>(IDS_KEY, (prev = []) => (on ? prev.filter((i) => i !== productId) : [...prev, productId])),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: IDS_KEY });
      qc.invalidateQueries({ queryKey: ["price-alerts", "list"] });
    },
  });
  if (!user) return null;
  const label = on ? "Price alert on" : "Price alert";
  const title = on ? "We'll tell you when it gets cheaper or is back in stock. Tap to turn off." : "Tell me when this gets cheaper or is back in stock";
  if (size === "small") {
    return (
      <button
        type="button"
        onClick={() => toggle.mutate()}
        disabled={toggle.isPending}
        aria-pressed={on}
        aria-label={label}
        title={title}
        className={`grid h-8 w-8 shrink-0 place-items-center rounded-full border transition-colors ${
          on ? "border-sage bg-sage-tint/50 text-sage-deep" : "border-line-strong text-ink-soft hover:border-sage hover:text-ink"
        }`}
      >
        <BellPlusIcon size={15} on={on} />
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={() => toggle.mutate()}
      disabled={toggle.isPending}
      aria-pressed={on}
      title={title}
      className={`tu-press flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full border px-5 text-[15.5px] font-semibold transition-colors ${
        on ? "border-sage bg-sage-tint/40 text-sage-deep" : "border-line-strong bg-surface text-ink hover:border-ink/40"
      }`}
    >
      <BellPlusIcon on={on} />
      {on ? "Price alert on ✓" : "Tell me if the price drops"}
    </button>
  );
}

/** /alerts: everything I watch, with the price then and now. */
export function PriceAlertsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace("/sign-in?next=/alerts");
  }, [isLoading, user, router]);
  const list = useQuery({ queryKey: ["price-alerts", "list"], queryFn: priceAlerts.list, enabled: !!user });
  const remove = useMutation({
    mutationFn: priceAlerts.remove,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["price-alerts"] });
    },
  });
  if (!user || list.isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  const items = list.data ?? [];
  return (
    <section className="tu-container pb-10 pt-3 lg:py-12">
      <div className="mx-auto max-w-[820px]">
        <h1 className="font-display text-[clamp(28px,4vw,40px)] leading-tight text-ink max-lg:hidden">Price alerts</h1>
        <p className="text-[15px] text-muted lg:mt-1 lg:text-[16px]">
          We check these shops every few hours and tell you (bell, phone, email) when something gets cheaper or is back in stock.
        </p>
        {items.length === 0 ? (
          <div className="mt-8 rounded-[22px] border border-dashed border-line p-10 text-center">
            <p className="text-[17px] font-semibold text-ink">No price alerts yet</p>
            <p className="mt-1 text-[15px] text-muted">Try something on, then press “Tell me if the price drops”.</p>
            <Button href="/try" size="md" className="mt-5">Go to the try-on studio</Button>
          </div>
        ) : (
          <div className="mt-6 space-y-3">
            {items.map((a) => {
              const change = a.price_cents - a.start_price_cents;
              return (
                <article key={a.product_id} className="flex items-center gap-4 rounded-[18px] border border-line bg-surface p-3 sm:p-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={relayedImageUrl(a.image_url, 240)} alt="" loading="lazy" className="h-20 w-16 shrink-0 rounded-lg bg-white object-contain" />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-[15px] text-ink">{a.name}</p>
                    <p className="mt-1 flex flex-wrap items-baseline gap-x-2 text-[14px]">
                      <b className="text-[17px] text-ink">{formatPrice(a.price_cents, a.currency)}</b>
                      {change < 0 && (
                        <span className="font-semibold text-sage-deep">
                          ↓ {formatPrice(-change, a.currency)} cheaper than when you set it
                        </span>
                      )}
                      {change > 0 && <span className="text-muted">was {formatPrice(a.start_price_cents, a.currency)}</span>}
                      {!a.in_stock && <span className="font-semibold text-[#a4553f]">Sold out for now</span>}
                    </p>
                    {a.shop && <p className="text-[13px] text-muted">{a.shop}</p>}
                  </div>
                  <div className="flex shrink-0 flex-col gap-1.5 sm:flex-row">
                    <Link href={`/try?product=${a.product_id}`} className="inline-flex min-h-[38px] items-center justify-center rounded-full bg-sage px-3.5 text-[13.5px] font-semibold text-white">
                      Try on
                    </Link>
                    <a href={affiliateGoUrl(a.product_id, "price_alert")} target="_blank" rel="noopener sponsored" className="inline-flex min-h-[38px] items-center justify-center rounded-full border border-line-strong px-3.5 text-[13.5px] font-semibold text-ink">
                      Shop ↗
                    </a>
                    <button type="button" onClick={() => remove.mutate(a.product_id)} className="min-h-[38px] rounded-full px-3 text-[13px] text-muted hover:text-[#a4553f]">
                      Remove
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
