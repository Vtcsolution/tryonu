"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AFTER_PAY_KEY } from "@/components/credits/BuyCreditsPanel";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { credits as creditsApi } from "@/lib/api/endpoints";
import { SESSION_QUERY_KEY } from "@/lib/auth/useSession";

type State =
  | { kind: "working" }
  | { kind: "succeeded"; credits: number | null; balance: number | null; plan: string | null; planUntil: string | null; apiTryons: number | null }
  | { kind: "pending" }
  | { kind: "failed"; message: string }
  | { kind: "cancelled" };

/** Where PayPal sends the shopper back. Asks our API to confirm the payment
 *  with PayPal (the API, not this page, decides whether money was taken),
 *  then shows the result. Safe to reload: a payment is only credited once. */
export function PayPalReturn() {
  const params = useSearchParams();
  const qc = useQueryClient();
  const paymentId = params.get("payment_id");
  const cancelled = params.get("cancelled") === "1";
  const [state, setState] = useState<State>(cancelled ? { kind: "cancelled" } : { kind: "working" });
  const started = useRef(false);
  // where the shopper was before buying (set by the credits page)
  const [afterPay, setAfterPay] = useState<string | null>(null);
  useEffect(() => {
    try {
      const next = sessionStorage.getItem(AFTER_PAY_KEY);
      if (next && next.startsWith("/") && !next.startsWith("//")) setAfterPay(next);
    } catch {
      // ignore
    }
  }, []);
  // PayPal can take a few seconds to finish: ask again by itself for about a minute
  const attempts = useRef(0);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (retry.current) clearTimeout(retry.current);
  }, []);

  const confirm = async (auto = false) => {
    if (!auto) attempts.current = 0;
    if (retry.current) clearTimeout(retry.current);
    if (!paymentId) {
      setState({ kind: "failed", message: "This link is missing its payment reference." });
      return;
    }
    if (!auto) setState({ kind: "working" });
    try {
      const res = await creditsApi.capturePurchase(paymentId);
      if (res.status === "succeeded") {
        setState({
          kind: "succeeded",
          credits: res.credits_granted,
          balance: res.new_balance,
          plan: res.plan_name ?? null,
          planUntil: res.plan_expires_at ?? null,
          apiTryons: res.developer_tryons ?? null,
        });
        qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
        qc.invalidateQueries({ queryKey: ["credit-history"] });
      } else if (res.status === "pending") {
        if (attempts.current < 15) {
          attempts.current += 1;
          setState({ kind: "working" });
          retry.current = setTimeout(() => void confirm(true), 4000);
        } else {
          setState({ kind: "pending" });
        }
      } else {
        setState({ kind: "failed", message: "The payment wasn't completed, so no credits were added." });
      }
    } catch (err) {
      setState({ kind: "failed", message: err instanceof ApiError ? err.detail : "We couldn't confirm the payment." });
    }
  };

  useEffect(() => {
    if (cancelled || started.current) return;
    started.current = true;
    void confirm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cancelled]);

  return (
    <section className="mx-auto w-[min(560px,calc(100%-42px))] py-20 text-center md:py-28">
      {state.kind === "working" && (
        <>
          <div className="mx-auto h-9 w-9 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
          <p className="mt-5 text-[16px] text-muted">Confirming your payment…</p>
        </>
      )}
      {state.kind === "succeeded" && (
        <>
          <h1 className="font-display text-[clamp(26px,4vw,36px)] text-ink">Payment complete</h1>
          {state.apiTryons ? (
            <>
              <p className="mt-3 text-[16px] text-muted">{state.apiTryons} API try-ons were added to your developer account.</p>
              <div className="mt-7 flex justify-center gap-3">
                <Button href="/developers/console#credits" size="md">Go to the developer console</Button>
              </div>
            </>
          ) : state.plan ? (
            <>
              <p className="mt-3 text-[16px] text-muted">
                Your {state.plan} plan is unlocked
                {state.planUntil ? ` until ${new Date(state.planUntil).toLocaleDateString()}` : ""}.
              </p>
              <div className="mt-7 flex justify-center gap-3">
                <Button href="/business" size="md">Go to my store</Button>
              </div>
            </>
          ) : (
            <>
              <p className="mt-3 text-[16px] text-muted">
                {state.credits ? `${state.credits} credits were added. ` : "Your credits were added. "}
                {state.balance !== null ? `Your balance is now ${state.balance} credits.` : ""}
              </p>
              <div className="mt-7 flex flex-wrap justify-center gap-3">
                {afterPay ? (
                  <Button href={afterPay} size="md">Continue your try-on →</Button>
                ) : (
                  <Button href="/try" size="md">Try something on</Button>
                )}
                <Button href="/credits" size="md" variant="outline">Back to credits</Button>
              </div>
            </>
          )}
        </>
      )}
      {state.kind === "pending" && (
        <>
          <h1 className="font-display text-[clamp(24px,4vw,32px)] text-ink">Payment not finished yet</h1>
          <p className="mt-3 text-[16px] text-muted">
            The payment isn&rsquo;t finished yet. If you paid, your credits arrive within a few minutes. If not, nothing was charged.
          </p>
          <div className="mt-7 flex justify-center gap-3">
            <Button size="md" onClick={() => void confirm()}>Check again</Button>
            <Button href="/credits" size="md" variant="outline">Back to credits</Button>
          </div>
        </>
      )}
      {state.kind === "failed" && (
        <>
          <h1 className="font-display text-[clamp(24px,4vw,32px)] text-ink">Payment not completed</h1>
          <p className="mt-3 text-[16px] text-muted">{state.message}</p>
          <div className="mt-7 flex justify-center gap-3">
            <Button size="md" onClick={() => void confirm()}>Try again</Button>
            <Button href="/credits" size="md" variant="outline">Back to credits</Button>
          </div>
        </>
      )}
      {state.kind === "cancelled" && (
        <>
          <h1 className="font-display text-[clamp(24px,4vw,32px)] text-ink">Payment cancelled</h1>
          <p className="mt-3 text-[16px] text-muted">You left the checkout before paying. Nothing was charged.</p>
          <p className="mt-7">
            <Link href="/credits" className="text-[15px] font-medium text-sage-deep underline-offset-2 hover:underline">
              Back to credits
            </Link>
          </p>
        </>
      )}
    </section>
  );
}
