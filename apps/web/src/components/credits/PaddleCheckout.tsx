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
  Initialize: (opts: { token: string; eventCallback?: (e: PaddleEvent) => void }) => void;
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

  const open = useCallback(async () => {
    const paddle = config.data?.paddle;
    if (!transactionId || !paddle) return;
    setProblem(null);
    try {
      const P = await loadPaddle();
      if (!initialized) {
        if (paddle.environment === "sandbox") P.Environment.set("sandbox");
        P.Initialize({
          token: paddle.token,
          eventCallback: (e) => {
            if (e.name === "checkout.completed") {
              paid.current = true;
              setTimeout(() => done(false), 1200); // let Paddle show its "thank you" for a moment
            }
            if (e.name === "checkout.closed" && !paid.current) done(true);
          },
        });
        initialized = true;
      }
      P.Checkout.open({ transactionId, settings: { displayMode: "overlay", variant: "one-page", locale: "en" } });
    } catch {
      setProblem("The secure checkout couldn't open. Check your internet, then try again.");
    }
  }, [config.data, transactionId, done]);

  useEffect(() => {
    if (config.data) open();
  }, [config.data, open]);

  const missing = !transactionId || (config.isSuccess && !config.data?.paddle);
  return (
    <section className="mx-auto flex min-h-[60vh] w-[min(560px,calc(100%-32px))] flex-col items-center justify-center py-16 text-center">
      {missing ? (
        <>
          <p className="text-[20px] font-semibold text-ink">This payment link isn&apos;t complete</p>
          <p className="mt-2 text-[15px] text-muted">Nothing was charged. Please start again from the price you chose.</p>
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
            <button type="button" onClick={open} className="tu-press rounded-full bg-sage px-6 py-3 text-[15.5px] font-semibold text-white">
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
