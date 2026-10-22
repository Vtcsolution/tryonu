"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { credits as creditsApi } from "@/lib/api/endpoints";

// Paddle.js v2 (the checkout card, PayPal, Apple Pay and Google Pay run inside it)
const PADDLE_JS = "https://cdn.paddle.com/paddle/v2/paddle.js";

type PaddleEvent = { name?: string };
type PaddleJs = {
  Environment: { set: (env: string) => void };
  Initialize: (opts: { token: string; checkout?: { settings: Record<string, unknown> }; eventCallback?: (e: PaddleEvent) => void }) => void;
  Checkout: { open: (opts: { transactionId: string; settings?: Record<string, unknown> }) => void };
};
declare global {
  interface Window {
    Paddle?: PaddleJs;
  }
}

function loadPaddle(): Promise<PaddleJs> {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = PADDLE_JS;
    script.async = true;
    script.onload = () => (window.Paddle ? resolve(window.Paddle) : reject(new Error("no Paddle")));
    script.onerror = () => reject(new Error("Paddle didn't load"));
    document.head.appendChild(script);
  });
}

let initialized = false;

/** /pay: Paddle sends the checkout link here (?_ptxn=…&payment_id=…). Opens Paddle's
 *  checkout; when paid, goes to /credits/paypal, which asks our API to confirm with
 *  Paddle (nothing this page says counts as paid). */
export function PaddleCheckout() {
  const router = useRouter();
  const params = useSearchParams();
  const transactionId = params.get("_ptxn");
  const paymentId = params.get("payment_id");
  const config = useQuery({ queryKey: ["checkout-config"], queryFn: creditsApi.checkoutConfig, staleTime: 5 * 60_000 });
  const [problem, setProblem] = useState<string | null>(null);
  const paid = useRef(false);

  const done = useCallback(
    (cancelled: boolean) => {
      if (!paymentId) return router.push("/credits");
      router.push(`/credits/paypal?payment_id=${encodeURIComponent(paymentId)}${cancelled ? "&cancelled=1" : ""}`);
    },
    [paymentId, router],
  );

  const opened = useRef(false);
  const open = useCallback(async (again = false) => {
    const paddle = config.data?.paddle;
    if (!transactionId || !paddle) return;
    setProblem(null);
    // after paying, Paddle itself sends the customer back to TryOnU's confirmation page
    const back = paymentId ? `${window.location.origin}/credits/paypal?payment_id=${encodeURIComponent(paymentId)}` : undefined;
    const settings = { displayMode: "overlay", variant: "one-page", locale: "en", ...(back ? { successUrl: back } : {}) };
    try {
      const P = await loadPaddle();
      if (!initialized) {
        if (paddle.environment === "sandbox") P.Environment.set("sandbox");
        // Paddle.js opens the checkout by itself for the ?_ptxn= in the address: same settings
        P.Initialize({
          token: paddle.token,
          checkout: { settings },
          eventCallback: (e) => {
            if (e.name === "checkout.loaded") opened.current = true;
            if (e.name === "checkout.completed") {
              paid.current = true;
              setTimeout(() => done(false), 1200); // let Paddle show its "thank you" for a moment
            }
            if (e.name === "checkout.closed" && !paid.current) done(true);
          },
        });
        initialized = true;
      }
      // opened by hand only when Paddle didn't open it by itself, or when asked again
      if (again) P.Checkout.open({ transactionId, settings });
      else
        setTimeout(() => {
          if (!opened.current) P.Checkout.open({ transactionId, settings });
        }, 1500);
    } catch {
      setProblem("The secure checkout couldn't open. Check your internet, then try again.");
    }
  }, [config.data, transactionId, paymentId, done]);

  useEffect(() => {
    if (config.data) open();
  }, [config.data, open]);

  // no transaction: the page was opened by itself, not from a Buy button;
  // no Paddle settings: card payments aren't switched on yet (admin: Paddle client-side token)
  const noLink = !transactionId;
  const notReady = !noLink && config.isSuccess && !config.data?.paddle;
  const missing = noLink || notReady;
  return (
    <section className="mx-auto flex min-h-[60vh] w-[min(560px,calc(100%-32px))] flex-col items-center justify-center py-16 text-center">
      {missing ? (
        <>
          <p className="text-[20px] font-semibold text-ink">{noLink ? "Choose what to buy first" : "Card payments aren't ready yet"}</p>
          <p className="mt-2 text-[15px] text-muted">
            {noLink
              ? "This page opens the payment after you press Buy. Nothing was charged."
              : "Nothing was charged. Please try again a little later, or contact us."}
          </p>
          <Link href="/credits" className="tu-press mt-6 rounded-full bg-sage px-6 py-3 text-[15.5px] font-semibold text-white">
            Back to credits
          </Link>
        </>
      ) : (
        <>
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-line-strong border-t-sage" aria-hidden="true" />
          <p className="mt-5 text-[19px] font-semibold text-ink">Opening secure checkout…</p>
          <p className="mt-1 text-[15px] text-muted">Pay by card, PayPal, Apple Pay or Google Pay.</p>
          {problem && <p className="mt-4 text-[14.5px] text-[#a4553f]">{problem}</p>}
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button type="button" onClick={() => open(true)} className="tu-press rounded-full bg-sage px-6 py-3 text-[15.5px] font-semibold text-white">
              Open checkout again
            </button>
            <button type="button" onClick={() => done(true)} className="rounded-full border border-line-strong px-6 py-3 text-[15.5px] font-semibold text-ink">
              Cancel
            </button>
          </div>
          <p className="mt-6 text-[12.5px] text-faint">Payments are handled by Paddle.com, our reseller and Merchant of Record.</p>
        </>
      )}
    </section>
  );
}
