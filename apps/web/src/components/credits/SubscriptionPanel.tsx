"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { subscriptions as subscriptionsApi } from "@/lib/api/endpoints";
import { SESSION_QUERY_KEY } from "@/lib/auth/useSession";
import type { SubscriptionPlanId } from "@/lib/api/types";

export function SubscriptionPanel() {
  const qc = useQueryClient();
  const [needsCardConfirmation, setNeedsCardConfirmation] = useState(false);

  const plansQuery = useQuery({ queryKey: ["subscription-plans"], queryFn: subscriptionsApi.plans });
  const currentQuery = useQuery({ queryKey: ["subscription-me"], queryFn: subscriptionsApi.me });

  const subscribe = useMutation({
    mutationFn: (plan: SubscriptionPlanId) => subscriptionsApi.subscribe(plan),
    onSuccess: (res) => {
      if (res.subscription.status === "active") {
        qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
        qc.invalidateQueries({ queryKey: ["subscription-me"] });
      } else {
        // Real Stripe path (requires_action) needs Stripe.js/Elements card
        // confirmation, not yet wired on the frontend — same honest
        // fallback as the one-off credit purchase flow.
        setNeedsCardConfirmation(true);
      }
    },
  });

  const cancel = useMutation({
    mutationFn: subscriptionsApi.cancel,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscription-me"] }),
  });

  const current = currentQuery.data;

  return (
    <div className="rounded-[22px] border border-line bg-surface p-6">
      <h2 className="font-display text-[18px] text-ink">Subscribe monthly</h2>
      <p className="mt-1 text-[13px] text-muted">Recurring credits every month — cancel anytime.</p>

      {current && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-sage/40 bg-sage-tint px-4 py-3">
          <p className="text-[13px] text-sage-deep">
            Current plan: <b className="capitalize">{current.plan}</b> · {current.credits_per_cycle} credits/mo
            {current.cancel_at_period_end && " · ending at period end"}
          </p>
          {!current.cancel_at_period_end && (
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="text-[12.5px] text-sage-deep underline hover:text-ink"
            >
              {cancel.isPending ? "Canceling…" : "Cancel"}
            </button>
          )}
        </div>
      )}

      {!current && plansQuery.data && (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {plansQuery.data.map((plan) => (
            <div key={plan.plan} className="rounded-[16px] border border-line p-4">
              <p className="font-display text-[16px] capitalize text-ink">{plan.name}</p>
              <p className="mt-1 text-[14px] text-muted">
                {(plan.price_cents / 100).toFixed(2)} {plan.currency.toUpperCase()}/mo
              </p>
              <p className="mt-1 text-[12px] text-faint">{plan.credits_per_cycle} credits/mo</p>
              <Button
                size="sm"
                className="mt-3 w-full"
                disabled={subscribe.isPending}
                onClick={() => {
                  setNeedsCardConfirmation(false);
                  subscribe.mutate(plan.plan);
                }}
              >
                {subscribe.isPending ? "Subscribing…" : "Subscribe"}
              </Button>
            </div>
          ))}
        </div>
      )}

      {subscribe.isError && (
        <p role="alert" className="mt-3 text-[13px] text-[#a4553f]">
          {subscribe.error instanceof ApiError ? subscribe.error.detail : "Couldn't start the subscription."}
        </p>
      )}
      {needsCardConfirmation && (
        <p className="mt-3 rounded-[14px] border border-line bg-paper-2 px-4 py-3 text-[13px] text-ink-soft">
          This plan needs card confirmation, which isn't connected yet — please try again shortly or contact
          support.
        </p>
      )}
    </div>
  );
}
