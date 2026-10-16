"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ShareLook } from "@/components/try/ShareLook";
import { RetailerTag, formatPrice } from "@/components/try/shop";
import { Button } from "@/components/ui/Button";
import { affiliateGoUrl, relayedImageUrl, resolveMediaUrl } from "@/lib/api/client";
import { savedLooks as savedLooksApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { SavedLook } from "@/lib/api/types";

type LookItem = NonNullable<SavedLook["items"]>[number];

/** The shopper's own lookbook: every saved look, with its products, shop links and Share. */
export function SavedLooksGallery() {
  const router = useRouter();
  const { user, isLoading: sessionLoading } = useSession();
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/saved");
  }, [sessionLoading, user, router]);

  const looksQuery = useQuery({
    queryKey: ["saved-looks"],
    queryFn: savedLooksApi.list,
    enabled: !!user,
  });
  const opened = looksQuery.data?.find((l) => l.id === openId) ?? null;

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(1600px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(1600px,calc(100%-32px))] py-12 md:py-16">
      <h1 className="font-display text-[clamp(28px,4vw,42px)] leading-tight text-ink">
        Your <em>saved looks</em>
      </h1>
      <p className="mt-2 max-w-2xl text-[16.5px] leading-relaxed text-ink-soft">
        Every look you saved, with its products. Open one to shop it, or press <b>Share</b> to send it to friends and social
        media: they can try the same products on themselves.
      </p>

      <div className="mt-8">
        {looksQuery.isLoading && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] animate-pulse rounded-[22px] bg-paper-2" />
            ))}
          </div>
        )}

        {looksQuery.data && looksQuery.data.length === 0 && (
          <div className="rounded-[22px] border border-dashed border-line p-10 text-center">
            <p className="text-[16px] text-muted">
              No saved looks yet. Try something on and press <b>Save this look</b> on the result.
            </p>
            <Button href="/try" size="md" className="mt-5">
              Start a try-on <span aria-hidden="true">→</span>
            </Button>
          </div>
        )}

        {looksQuery.data && looksQuery.data.length > 0 && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {looksQuery.data.map((look) => (
              <SavedLookCard key={look.id} look={look} onOpen={() => setOpenId(look.id)} />
            ))}
          </div>
        )}
      </div>

      {opened && <LookDetail look={opened} onClose={() => setOpenId(null)} />}
    </section>
  );
}

function lookTitle(look: SavedLook): string {
  const items = look.items ?? [];
  if (look.title) return look.title;
  if (items.length === 1) return items[0].name;
  if (items.length > 1) return `${items.length}-item outfit`;
  return look.product?.name ?? "Saved look";
}

function lookPrice(look: SavedLook): string | null {
  return look.total_cents != null && look.currency ? formatPrice(look.total_cents, look.currency) : null;
}

function SavedLookCard({ look, onOpen }: { look: SavedLook; onOpen: () => void }) {
  const qc = useQueryClient();
  const [confirmRemove, setConfirmRemove] = useState(false);
  const remove = useMutation({
    mutationFn: () => savedLooksApi.remove(look.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-looks"] }),
  });
  const image = resolveMediaUrl(look.image_url);
  const items = look.items ?? [];
  const price = lookPrice(look);

  return (
    <article className="flex flex-col overflow-hidden rounded-[22px] border border-line bg-surface">
      <button type="button" onClick={onOpen} className="group relative block aspect-[3/4] bg-paper-2" aria-label={`Open ${lookTitle(look)}`}>
        {image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={image}
            alt={lookTitle(look)}
            loading="lazy"
            className="h-full w-full object-cover object-top transition-transform duration-300 group-hover:scale-[1.02]"
          />
        )}
        <span className="absolute bottom-3 left-3 rounded-full bg-black/60 px-3 py-1.5 text-[13px] font-semibold text-white backdrop-blur">
          View &amp; shop →
        </span>
      </button>

      <div className="flex flex-1 flex-col p-4">
        <p className="truncate text-[16.5px] font-semibold text-ink">{lookTitle(look)}</p>
        <p className="mt-0.5 text-[14px] text-muted">
          {items.length > 0 ? `${items.length} ${items.length === 1 ? "product" : "products"}` : "Your own item"}
          {price ? ` · ${price}` : ""} · {new Date(look.created_at).toLocaleDateString()}
        </p>

        {items.length > 0 && (
          <div className="mt-3 flex gap-1.5">
            {items.slice(0, 5).map((item) => (
              <Thumb key={item.id} item={item} className="h-12 w-12 rounded-[10px]" />
            ))}
            {items.length > 5 && (
              <span className="grid h-12 w-12 place-items-center rounded-[10px] bg-paper-2 text-[13px] font-semibold text-ink-soft">
                +{items.length - 5}
              </span>
            )}
          </div>
        )}

        <div className="mt-auto space-y-2 pt-4">
          {look.tryon_job_id && <ShareLook jobId={look.tryon_job_id} variant="wide" />}
          <button
            type="button"
            onClick={onOpen}
            className="tu-press min-h-[44px] w-full rounded-full border border-line-strong text-[15px] font-semibold text-ink hover:border-ink/40"
          >
            Shop this look
          </button>
          <div className="pt-1 text-center text-[13.5px]">
            {confirmRemove ? (
              <span className="inline-flex flex-wrap items-center justify-center gap-3 text-ink-soft">
                Remove from saved looks?
                <button
                  type="button"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate()}
                  className="font-semibold text-[#a4553f] hover:underline"
                >
                  Yes, remove
                </button>
                <button type="button" onClick={() => setConfirmRemove(false)} className="text-muted hover:text-ink">
                  Cancel
                </button>
              </span>
            ) : (
              <button type="button" onClick={() => setConfirmRemove(true)} className="text-muted hover:text-[#a4553f]">
                Remove
              </button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

function Thumb({ item, className = "" }: { item: LookItem; className?: string }) {
  const direct = resolveMediaUrl(item.image_url);
  const [src, setSrc] = useState(relayedImageUrl(item.image_url, 300));
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

/** One saved look, large: the picture, every product with Shop now, and Share. */
function LookDetail({ look, onClose }: { look: SavedLook; onClose: () => void }) {
  const image = resolveMediaUrl(look.image_url);
  const items = look.items ?? [];
  const price = lookPrice(look);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-[90] overflow-y-auto bg-black/60 p-3 sm:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={lookTitle(look)}
        className="relative mx-auto my-4 grid w-full max-w-[1180px] gap-6 rounded-[26px] bg-surface p-4 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 z-10 grid h-11 w-11 place-items-center rounded-full bg-paper-2 text-[24px] text-ink hover:bg-line"
        >
          ×
        </button>
        <div className="overflow-hidden rounded-[20px] bg-paper-2">
          {image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={image} alt={lookTitle(look)} className="h-auto w-full" />
          )}
        </div>
        <div className="flex min-w-0 flex-col">
          <p className="pr-12 text-[12.5px] uppercase tracking-[0.14em] text-faint">
            {items.length > 1 ? `${items.length}-item outfit` : "Saved look"}
            {price ? ` · ${price}` : ""}
          </p>
          <h2 className="mt-1 pr-12 font-display text-[28px] leading-tight text-ink">{lookTitle(look)}</h2>

          {items.length > 0 ? (
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {items.map((item) => (
                <a
                  key={item.id}
                  href={affiliateGoUrl(item.id, "saved_look")}
                  target="_blank"
                  rel="noopener sponsored"
                  className="relative block overflow-hidden rounded-[14px] border border-line bg-surface"
                >
                  <span className="relative block">
                    <Thumb item={item} className="aspect-square w-full border-0" />
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
                    <span className="block text-[15px] text-ink">{item.name}</span>
                    <span className="block text-[13.5px] text-muted">
                      {formatPrice(item.price_cents, item.currency)}
                      {item.shop ? ` · ${item.shop}` : ""}
                    </span>
                  </span>
                  <Button
                    href={affiliateGoUrl(item.id, "saved_look")}
                    size="sm"
                    variant="outline"
                    className="shrink-0"
                  >
                    Shop now
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="mt-auto pt-6">
            {look.tryon_job_id && <ShareLook jobId={look.tryon_job_id} variant="wide" />}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
