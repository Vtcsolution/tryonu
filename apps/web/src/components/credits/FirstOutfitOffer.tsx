"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { formatPrice } from "@/components/try/shop";
import { credits as creditsApi } from "@/lib/api/endpoints";
import type { CreditPackage } from "@/lib/api/types";
import { useSession } from "@/lib/auth/useSession";

/** The first-purchase offer (the $1 first outfit), while this visitor can still
 * buy it: everyone without an account, and members who never bought credits. */
export function useFirstOffer(): CreditPackage | null {
  const { user, isLoading } = useSession();
  const packs = useQuery({
    queryKey: ["credit-packages", user?.id ?? "visitor"],
    queryFn: creditsApi.packages,
    enabled: !isLoading,
    staleTime: 5 * 60_000,
  });
  return packs.data?.find((p) => p.new_members_only) ?? null;
}

/** Where the offer button goes: straight to it on the credits page, or
 * through sign-up first (it comes back to the offer after). */
function offerHref(signedIn: boolean, next?: string): string {
  const credits = `/credits?offer=1${next ? `&next=${encodeURIComponent(next)}` : ""}`;
  return signedIn ? credits : `/sign-up?next=${encodeURIComponent(credits)}`;
}

/**
 * "Try a complete outfit for just $1". Shown in several places; gently pulses
 * and shines so people notice it, and disappears once the member has bought
 * credits. `next`: where to go after paying (the try-on they were on).
 */
export function FirstOutfitOffer({
  variant = "button",
  next,
  className = "",
  fallback = null,
}: {
  variant?: "button" | "banner" | "light" | "compact";
  next?: string;
  className?: string;
  /** shown instead once the offer is gone (the header's normal "Try it now") */
  fallback?: ReactNode;
}) {
  const offer = useFirstOffer();
  const { user } = useSession();
  if (!offer) return <>{fallback}</>;
  const price = formatPrice(offer.price_cents, offer.currency).replace(/\.00$/, "");
  const href = offerHref(!!user, next);

  if (variant === "compact") {
    // the header: small, same pulse and shine
    return (
      <Link
        href={href}
        title={`${offer.credits} credits for ${price}: one complete outfit on your photo. First purchase only.`}
        className={`tu-press tu-attention tu-shine relative inline-flex min-h-[40px] items-center justify-center gap-1.5 overflow-hidden whitespace-nowrap rounded-full bg-sage px-4 text-[14.5px] font-semibold text-white hover:bg-sage-deep ${className}`}
      >
        Full outfit for {price} <span aria-hidden="true">→</span>
      </Link>
    );
  }

  if (variant === "banner") {
    return (
      <div className={`tu-shine relative overflow-hidden rounded-[22px] border border-sage/50 bg-sage-tint/40 p-4 sm:p-5 ${className}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[12.5px] font-semibold uppercase tracking-[0.14em] text-sage-deep">New members</p>
            <p className="mt-0.5 font-display text-[22px] leading-tight text-ink">
              Try a complete outfit for just <em>{price}</em>
            </p>
            <p className="mt-0.5 text-[14.5px] text-ink-soft">
              {offer.credits} credits, enough for one whole look. Your first purchase only.
            </p>
          </div>
          <Link
            href={href}
            className="tu-press tu-attention inline-flex min-h-[48px] shrink-0 items-center rounded-full bg-sage px-6 text-[16px] font-semibold text-white hover:bg-sage-deep"
          >
            Get it for {price} <span aria-hidden="true" className="ml-1.5">→</span>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className={`tu-press tu-attention tu-shine relative inline-flex min-h-[52px] items-center justify-center gap-2 overflow-hidden rounded-full px-6 text-[16.5px] font-semibold ${
        variant === "light" ? "bg-white text-[#1c1b17] hover:bg-white/90" : "bg-sage text-white hover:bg-sage-deep"
      } ${className}`}
    >
      Try a complete outfit for just {price} <span aria-hidden="true">→</span>
    </Link>
  );
}
