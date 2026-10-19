"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PostToCommunity } from "@/components/community/PostToCommunity";
import { ShareLook } from "@/components/try/ShareLook";
import { RetailerTag, formatPrice } from "@/components/try/shop";
import { Button } from "@/components/ui/Button";
import { affiliateGoUrl, relayedImageUrl, resolveMediaUrl } from "@/lib/api/client";
import { PriceAlertButton } from "@/components/alerts/PriceAlerts";
import { savedLooks as savedLooksApi } from "@/lib/api/endpoints";
import type { SavedLook } from "@/lib/api/types";
import { useSession } from "@/lib/auth/useSession";

type LookItem = NonNullable<SavedLook["items"]>[number];

export function lookTitle(look: SavedLook): string {
  const items = look.items ?? [];
  if (look.title) return look.title;
  if (items.length === 1) return items[0].name;
  if (items.length > 1) return `${items.length}-item outfit`;
  return look.product?.name ?? "Saved look";
}

export function lookPrice(look: SavedLook): string | null {
  return look.total_cents != null && look.currency ? formatPrice(look.total_cents, look.currency) : null;
}

/** A product photo through TryOnU's relay, falling back to the shop's own link. */
export function LookThumb({ item, className = "" }: { item: LookItem; className?: string }) {
  const direct = resolveMediaUrl(item.image_url);
  const [src, setSrc] = useState(relayedImageUrl(item.image_url, 400));
  return (
    <span className={`block shrink-0 overflow-hidden border border-line bg-white ${className}`}>
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={item.name}
          loading="lazy"
          onError={() => direct && src !== direct && setSrc(direct)}
          className="h-full w-full object-contain"
        />
      )}
    </span>
  );
}

/** /saved/<id>: one saved look on its own page: the full picture, every product
 * with Shop now, and Share. */
export function SavedLookDetail({ id }: { id: string }) {
  const router = useRouter();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace(`/sign-in?next=${encodeURIComponent(`/saved/${id}`)}`);
  }, [isLoading, user, router, id]);
  const looks = useQuery({ queryKey: ["saved-looks"], queryFn: savedLooksApi.list, enabled: !!user });
  const look = looks.data?.find((l) => l.id === id);

  if (!user || looks.isLoading) {
    return (
      <section className="mx-auto py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }
  if (!look) {
    return (
      <section className="mx-auto w-[min(640px,calc(100%-32px))] py-20 text-center">
        <p className="font-display text-[26px] text-ink">This look isn&apos;t in your saved looks</p>
        <Button href="/saved" size="md" className="mt-5">Back to saved looks</Button>
      </section>
    );
  }

  const image = resolveMediaUrl(look.image_url);
  const items = look.items ?? [];
  const price = lookPrice(look);

  return (
    <section className="tu-container py-8 md:py-12">
      <div className="flex flex-wrap items-center gap-3">
        <Button href="/saved" size="sm" variant="outline">← All saved looks</Button>
        <div className="ml-auto">{look.tryon_job_id && <ShareLook jobId={look.tryon_job_id} />}</div>
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-8">
        <figure className="overflow-hidden rounded-[26px] border border-line bg-paper-2">
          {image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={image} alt={lookTitle(look)} className="h-auto w-full" />
          )}
          <figcaption className="border-t border-line bg-surface px-4 py-2.5 text-[13px] text-muted">
            Saved {new Date(look.created_at).toLocaleDateString()} · AI try-on result
          </figcaption>
        </figure>

        <div className="flex min-w-0 flex-col rounded-[26px] border border-line bg-surface p-5 md:p-6">
          <p className="text-[12.5px] uppercase tracking-[0.14em] text-faint">
            {items.length > 1 ? `${items.length}-item outfit` : "Saved look"}
            {price ? ` · ${price}` : ""}
          </p>
          <h1 className="mt-1 font-display text-[clamp(26px,3vw,34px)] leading-tight text-ink">{lookTitle(look)}</h1>

          {items.length > 0 ? (
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {items.map((item) => (
                <a
                  key={item.id}
                  href={affiliateGoUrl(item.id, "saved_look")}
                  target="_blank"
                  rel="noopener sponsored"
                  className="block overflow-hidden rounded-[14px] border border-line bg-surface"
                >
                  <span className="relative block">
                    <LookThumb item={item} className="aspect-square w-full border-0" />
                    <RetailerTag name={item.shop} className="absolute left-1.5 top-1.5" />
                    {item.on_photo != null && (
                      <span
                        className={`absolute bottom-1.5 left-1.5 rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${
                          item.on_photo ? "bg-sage text-white" : "bg-surface/95 text-ink-soft"
                        }`}
                      >
                        {item.on_photo ? "on photo" : "matched"}
                      </span>
                    )}
                  </span>
                  <p className="truncate px-2 py-1.5 text-[12.5px] text-ink-soft">{item.name}</p>
                </a>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-[15px] text-muted">This look uses your own item, so there is nothing to shop.</p>
          )}

          {items.length > 0 && (
            <div className="mt-5 space-y-3 border-t border-line pt-4">
              {items.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3">
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15.5px] text-ink">{item.name}</span>
                    <span className="block text-[13.5px] text-muted">
                      {formatPrice(item.price_cents, item.currency)}
                      {item.shop ? ` · ${item.shop}` : ""}
                    </span>
                  </span>
                  <PriceAlertButton productId={item.id} size="small" />
                  <Button href={affiliateGoUrl(item.id, "saved_look")} size="sm" variant="outline" className="shrink-0">
                    Shop now
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="mt-auto space-y-3 pt-6">
            {look.tryon_job_id && <ShareLook jobId={look.tryon_job_id} variant="wide" />}
            {look.tryon_job_id && <PostToCommunity jobId={look.tryon_job_id} imageUrl={look.image_url} />}
            <Button href="/saved#earn" size="md" variant="outline" className="w-full">
              Invite friends &amp; earn credits
            </Button>
            <Button href="/try" size="md" variant="outline" className="w-full">
              Try another look
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
