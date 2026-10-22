"use client";

import { useQuery } from "@tanstack/react-query";
import { credits } from "@/lib/api/endpoints";

/** Which checkout payments open right now: "paddle", "paypal", or null while loading. */
export function useCheckoutProvider(): string | null {
  const config = useQuery({ queryKey: ["checkout-config"], queryFn: credits.checkoutConfig, staleTime: 5 * 60_000 });
  return config.data?.provider ?? null;
}

/** How customers can pay, in plain words. */
export const payWays = (provider: string | null) =>
  provider === "paddle" ? "card, PayPal, Apple Pay or Google Pay" : "PayPal or a card";
