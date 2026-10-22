"use client";

import { PayMethodPicker } from "@/components/credits/PayMethodPicker";
import { payWays, payWaysOf, useCheckoutProvider, useGateways } from "@/lib/useCheckout";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { credits as creditsApi } from "@/lib/api/endpoints";
import { SESSION_QUERY_KEY, useSession } from "@/lib/auth/useSession";
import { SubscriptionPanel } from "@/components/credits/SubscriptionPanel";
import { subscriptions as subscriptionsApi } from "@/lib/api/endpoints";
import type { CreditPackage } from "@/lib/api/types";

export const AFTER_PAY_KEY = "tou_after_pay";

export function BuyCreditsPanel() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, isLoading: sessionLoading } = useSession();
  const [selected, setSelected] = useState<CreditPackage | null>(null);
  const [needsCardConfirmation, setNeedsCardConfirmation] = useState(false);

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/credits");
  }, [sessionLoading, user, router]);

  const packagesQuery = useQuery({
    queryKey: ["credit-packages"],
    queryFn: creditsApi.packages,
    enabled: !!user,
  });

  const pricingQuery = useQuery({ queryKey: ["credit-pricing"], queryFn: creditsApi.pricing });
  const tryOnCost = pricingQuery.data
    ? Math.max(pricingQuery.data.tryon_cost, pricingQuery.data.outfit_tryon_cost)
    : null;

  const historyQuery = useQuery({
    queryKey: ["credit-history"],
    queryFn: creditsApi.history,
    enabled: !!user,
  });

  const checkoutProvider = useCheckoutProvider();
  const gateways = useGateways();
  const [payWith, setPayWith] = useState<string | null>(null);
  // monthly plans: shown only when there are some (or the member already has one)
  const subPlans = useQuery({ queryKey: ["subscription-plans"], queryFn: subscriptionsApi.plans, enabled: !!user });
  const subMine = useQuery({ queryKey: ["subscription-me"], queryFn: subscriptionsApi.me, enabled: !!user });
  const monthly = !!subMine.data || (subPlans.data?.length ?? 0) > 0;
  const purchase = useMutation({
    mutationFn: (pkg: CreditPackage) => creditsApi.purchase({ credit_package_id: pkg.id }, payWith),
    onSuccess: (res) => {
      if (res.status === "succeeded") {
        qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
        qc.invalidateQueries({ queryKey: ["credit-history"] });
      } else if (res.checkout_url) {
        // PayPal: pay on PayPal's page; it sends the shopper back to /credits/paypal,
        // which then offers to continue where they were (?next=)
        const next = new URLSearchParams(window.location.search).get("next");
        try {
          if (next && next.startsWith("/") && !next.startsWith("//")) sessionStorage.setItem(AFTER_PAY_KEY, next);
          else sessionStorage.removeItem(AFTER_PAY_KEY);
        } catch {
          // private window: they land on the normal "Try something on"
        }
        window.location.assign(res.checkout_url);
      } else {
        // Real card payments (Stripe requires_action) need client-side
        // confirmation via Stripe.js/Elements, not yet wired on the
        // frontend — the backend correctly hands back client_secret for
        // when that lands, but we don't pretend to complete it here.
        setNeedsCardConfirmation(true);
      }
    },
  });

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(880px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(880px,calc(100%-32px))] pb-10 pt-4 lg:py-20">
      <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink max-lg:hidden">
        Buy <em>credits</em>
      </h1>
      <p className="max-w-lg text-[16px] leading-relaxed text-muted lg:mt-3">
        You currently have <b className="text-ink">{user.credits_balance} credits</b>.
        {tryOnCost !== null ? ` Each try-on uses ${tryOnCost} credits.` : " Each try-on uses a few credits."}
      </p>

      {monthly && (
        <>
          <div className="mt-8">
            <SubscriptionPanel />
          </div>
          <div className="mt-10 flex items-center gap-3 text-[13px] text-faint">
            <span className="h-px flex-1 bg-line" />
            or buy one-time credits
            <span className="h-px flex-1 bg-line" />
          </div>
        </>
      )}

      {packagesQuery.data && packagesQuery.data.length > 0 && (
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {packagesQuery.data.map((pkg) => (
            <button
              key={pkg.id}
              type="button"
              onClick={() => {
                setSelected(pkg);
                setNeedsCardConfirmation(false);
                purchase.reset();
              }}
              className={`rounded-[20px] border p-5 text-left transition-colors ${
                selected?.id === pkg.id ? "border-sage ring-2 ring-sage/30" : "border-line hover:border-line-strong"
              }`}
            >
              <p className="font-display text-[20px] text-ink">{pkg.credits} credits</p>
              <p className="mt-1 text-[16px] text-muted">
                {(pkg.price_cents / 100).toFixed(2)} {pkg.currency.toUpperCase()}
              </p>
              {tryOnCost !== null && (
                <p className="mt-2 text-[14px] font-medium text-sage-deep">
                  {Math.floor(pkg.credits / tryOnCost)} try-on{Math.floor(pkg.credits / tryOnCost) === 1 ? "" : "s"}
                </p>
              )}
              <p className="mt-3 text-[13px] text-faint">{pkg.name}</p>
            </button>
          ))}
        </div>
      )}

      {packagesQuery.data && packagesQuery.data.length === 0 && (
        <p className="mt-8 text-[15px] text-muted">No credit packages are available right now.</p>
      )}

      <div className="mt-6 space-y-3">
        {purchase.isError && (
          <p role="alert" className="text-[14px] text-[#a4553f]">
            {purchase.error instanceof ApiError ? purchase.error.detail : "Couldn't start the purchase."}
          </p>
        )}
        {purchase.isSuccess && purchase.data.status === "succeeded" && (
          <p className="rounded-[16px] border border-sage/40 bg-sage-tint px-4 py-3 text-[14px] text-sage-deep">
            {purchase.data.credits_granted} credits added — new balance {purchase.data.new_balance}.
          </p>
        )}
        {needsCardConfirmation && (
          <p className="rounded-[16px] border border-line bg-paper-2 px-4 py-3 text-[14px] text-ink-soft">
            Card payment isn't ready yet. Please try again later, or contact us.
          </p>
        )}

        <PayMethodPicker value={payWith} onChange={setPayWith} />
        <Button
          size="md"
          disabled={!selected || purchase.isPending}
          onClick={() => selected && purchase.mutate(selected)}
        >
          {purchase.isPending
            ? "Opening checkout…"
            : purchase.isSuccess && purchase.data.checkout_url
              ? checkoutProvider === "paddle"
                ? "Opening secure checkout…"
                : "Redirecting to PayPal…"
              : selected
                ? `Buy ${selected.credits} credits`
                : "Select a package"}
        </Button>
        <p className="text-[13px] text-faint">Secure payment. Pay by {gateways.length ? payWaysOf(gateways) : payWays(checkoutProvider)}.</p>
      </div>

      {historyQuery.data && historyQuery.data.length > 0 && (
        <div className="mt-14">
          <h2 className="font-display text-[18px] text-ink">Recent activity</h2>
          <div className="mt-4 divide-y divide-line rounded-[20px] border border-line bg-surface">
            {historyQuery.data.slice(0, 10).map((tx) => (
              <div key={tx.id} className="flex items-center justify-between px-4 py-3 text-[14px]">
                <span className="text-ink-soft">{tx.note || tx.reason.replace(/_/g, " ")}</span>
                <span className={tx.amount >= 0 ? "font-semibold text-sage-deep" : "font-semibold text-ink-soft"}>
                  {tx.amount >= 0 ? "+" : ""}
                  {tx.amount}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
