"use client";

import { useQuery } from "@tanstack/react-query";
import { credits } from "@/lib/api/endpoints";

export type Gateway = { id: string; label: string };

function useConfig() {
  return useQuery({ queryKey: ["checkout-config"], queryFn: credits.checkoutConfig, staleTime: 5 * 60_000 });
}

/** The default checkout right now: "paddle", "paypal", or null while loading. */
export function useCheckoutProvider(): string | null {
  return useConfig().data?.provider ?? null;
}

/** Every payment gateway switched on in Admin, in order (the default first). */
export function useGateways(): Gateway[] {
  return useConfig().data?.gateways ?? [];
}

/** How customers can pay, in plain words. */
export const payWays = (provider: string | null) =>
  provider === "paddle" ? "card, PayPal, Apple Pay or Google Pay" : "PayPal or a card";

/** The same, from every gateway switched on. */
export function payWaysOf(gateways: Gateway[]): string {
  if (gateways.length === 0) return "card or PayPal";
  const ways = new Set<string>();
  for (const g of gateways) {
    if (g.id === "paddle") ["card", "PayPal", "Apple Pay", "Google Pay"].forEach((w) => ways.add(w));
    else if (g.id === "paypal") ways.add("PayPal");
    else ways.add("card");
  }
  const list = [...ways];
  return list.length > 1 ? `${list.slice(0, -1).join(", ")} or ${list[list.length - 1]}` : list[0];
}
