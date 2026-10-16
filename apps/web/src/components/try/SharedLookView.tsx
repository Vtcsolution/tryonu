"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { rememberReferral } from "@/components/referrals/ReferralCapture";
import { ShareLook } from "@/components/try/ShareLook";
import { RetailerTag, formatPrice } from "@/components/try/shop";
import { ApiError, relayedImageUrl, resolveMediaUrl } from "@/lib/api/client";
import { shared as sharedApi } from "@/lib/api/endpoints";
import type { SharedLook } from "@/lib/api/types";
import { useSession } from "@/lib/auth/useSession";

type SharedProduct = SharedLook["products"][number];

/** What anyone with a shared look's link sees: the same picture and products
 * as the owner's result page, shop links, and "Try this look on yourself". */
export function SharedLookView({ look, pageUrl }: { look: SharedLook; pageUrl: string }) {
  const count = look.products.length;
  useEffect(() => rememberReferral(`look:${look.token}`), [look.token]);
  return (
    <section className="mx-auto w-[min(1280px,calc(100%-32px))] py-8 md:py-12">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">A look made with TryOnU</p>
          <h1 className="mt-1 font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">{look.title}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ShareLook url={pageUrl} />
          <TryThisLookButton token={look.token} compact />
        </div>
      </div>

      <figure className="mx-auto mt-6 max-w-[760px] overflow-hidden rounded-[28px] border border-line bg-paper-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={look.image_url} alt={`AI try-on: ${look.title}`} className="h-auto w-full" />
        <figcaption className="flex items-center justify-between gap-2 border-t border-line bg-surface px-4 py-2.5 text-[13px] text-muted">
          <span>AI-generated try-on. Fit, size and colour may differ in real life.</span>
          <span className="shrink-0 rounded-full bg-sage px-2.5 py-1 text-[11.5px] font-semibold text-white">AI try-on result</span>
        </figcaption>
      </figure>

      {count > 0 && (
        <div className="mt-8 rounded-[26px] border border-line bg-surface p-5 md:p-7">
          <p className="text-[12.5px] uppercase tracking-[0.14em] text-faint">
            {count === 1 ? "1 item" : `${count}-item outfit`}
            {look.total_cents != null && look.currency ? ` · ${formatPrice(look.total_cents, look.currency)}` : ""}
          </p>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {look.products.map((p) => (
              <ProductThumb key={p.id} product={p} />
            ))}
          </div>

          <div className="mt-6 space-y-3 border-t border-line pt-5">
            {look.products.map((p) => (
              <div key={p.id} className="flex items-center justify-between gap-3">
                <span className="min-w-0 flex-1">
                  <span className="block text-[15.5px] text-ink">{p.name}</span>
                  <span className="block text-[13.5px] text-muted">
                    {formatPrice(p.price_cents, p.currency)}
                    {p.shop ? ` · ${p.shop}` : ""}
                  </span>
                </span>
                <a
                  href={p.buy_url}
                  target="_blank"
                  rel="noopener sponsored"
                  className="tu-press inline-flex min-h-[40px] shrink-0 items-center rounded-full border border-line-strong px-4 text-[14px] font-semibold text-ink hover:border-ink/40"
                >
                  Shop now
                </a>
              </div>
            ))}
          </div>

          <div className="mt-7 rounded-[22px] border border-sage/40 bg-sage-tint/25 p-5 text-center md:p-6">
            <p className="font-display text-[24px] text-ink">
              See this look on <em>you</em>
            </p>
            <p className="mx-auto mt-1 max-w-[520px] text-[15px] text-ink-soft">
              Create your account, add one photo of yourself, and we put {count === 1 ? "this product" : `all ${count} products`} on
              you.
            </p>
            <div className="mx-auto mt-4 max-w-[440px]">
              <TryThisLookButton token={look.token} />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ProductThumb({ product }: { product: SharedProduct }) {
  const direct = resolveMediaUrl(product.image_url);
  const [src, setSrc] = useState(relayedImageUrl(product.image_url, 600));
  return (
    <a
      href={product.buy_url}
      target="_blank"
      rel="noopener sponsored"
      className="group relative block overflow-hidden rounded-[16px] border border-line bg-surface"
    >
      <div className="relative aspect-square bg-white">
        {src && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={product.name}
            loading="lazy"
            onError={() => direct && src !== direct && setSrc(direct)}
            className="h-full w-full object-contain transition-transform group-hover:scale-[1.02]"
          />
        )}
        <RetailerTag name={product.shop} className="absolute left-2 top-2" />
        {product.on_photo != null && (
          <span
            className={`absolute bottom-2 left-2 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              product.on_photo ? "bg-sage text-white" : "bg-surface/95 text-ink-soft"
            }`}
          >
            {product.on_photo ? "on photo" : "matched"}
          </span>
        )}
      </div>
      <p className="truncate px-2.5 py-2 text-[13px] text-ink-soft">{product.name}</p>
    </a>
  );
}

/** Signed in: the look's products become the visitor's own outfit on the try-on page.
 * Not signed in: create an account first, then straight back here. */
function TryThisLookButton({ token, compact = false }: { token: string; compact?: boolean }) {
  const router = useRouter();
  const { user, isLoading } = useSession();
  const start = useMutation({
    mutationFn: () => sharedApi.tryThis(token),
    onSuccess: (res) => {
      router.push(res.outfit_id ? `/try?outfit=${res.outfit_id}` : `/try?product=${res.product_id}`);
    },
  });
  const go = () => {
    if (!user) {
      router.push(`/sign-up?next=${encodeURIComponent(`/look/${token}/try`)}`);
      return;
    }
    start.mutate();
  };
  const label = start.isPending ? "Getting it ready…" : "Try this look on yourself";
  return (
    <div className={compact ? "" : "w-full"}>
      <button
        type="button"
        onClick={go}
        disabled={isLoading || start.isPending}
        className={`tu-press inline-flex items-center justify-center gap-2 rounded-full bg-ink font-semibold text-surface hover:bg-ink/90 disabled:opacity-60 ${
          compact ? "min-h-[44px] px-5 text-[15px]" : "min-h-[52px] w-full px-6 text-[17px]"
        }`}
      >
        <span aria-hidden="true">✨</span> {label}
      </button>
      {start.isError && (
        <p role="alert" className="mt-2 text-[14px] text-[#a4553f]">
          {start.error instanceof ApiError ? start.error.detail : "Couldn't open this look. Please try again."}
        </p>
      )}
    </div>
  );
}
