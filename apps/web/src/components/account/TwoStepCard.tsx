"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";
import type { User } from "@/lib/api/types";
import { SESSION_QUERY_KEY } from "@/lib/auth/useSession";

const card = "rounded-[24px] border border-line bg-surface p-4 sm:p-7";
const codeField =
  "h-12 w-40 rounded-xl border border-line-strong bg-paper px-3.5 text-center text-[20px] tracking-[0.3em] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25";

const errorOf = (e: unknown) => (e instanceof ApiError ? e.detail : "Something went wrong. Please try again.");

/** Two-step sign-in: a 6-digit code from an authenticator app as well as the password. */
export function TwoStepCard({ user }: { user: User }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const setup = useMutation({ mutationFn: auth.twoStepSetup });
  const enable = useMutation({
    mutationFn: () => auth.twoStepEnable(code),
    onSuccess: (u) => {
      qc.setQueryData(SESSION_QUERY_KEY, u);
      setCode("");
      setup.reset();
    },
  });
  const disable = useMutation({
    mutationFn: () => auth.twoStepDisable(code),
    onSuccess: (u) => {
      qc.setQueryData(SESSION_QUERY_KEY, u);
      setCode("");
    },
  });
  const on = !!user.totp_enabled;
  const input = (
    <input
      inputMode="numeric"
      autoComplete="one-time-code"
      value={code}
      onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
      placeholder="123456"
      aria-label="6-digit code"
      className={codeField}
    />
  );

  return (
    <section className={card}>
      <h2 className="font-display text-[22px] text-ink">Two-step sign-in</h2>
      {on ? (
        <>
          <p className="mt-2 text-[15px] text-ink">
            <b className="text-sage-deep">On.</b> Signing in asks for the 6-digit code from your authenticator app as
            well as your password.
          </p>
          <p className="mt-4 text-[14.5px] text-muted">To turn it off, type the current code from the app:</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            {input}
            <Button size="md" variant="outline" disabled={code.length !== 6 || disable.isPending} onClick={() => disable.mutate()}>
              {disable.isPending ? "Turning off…" : "Turn off"}
            </Button>
          </div>
          {disable.isError && <p className="mt-2 text-[14px] text-[#a4553f]">{errorOf(disable.error)}</p>}
        </>
      ) : !setup.data ? (
        <>
          <p className="mt-2 text-[15px] text-muted">
            Keep your account safe even if someone learns your password: signing in will also ask for a code from an app
            on your phone (Google Authenticator, Microsoft Authenticator or Authy).
          </p>
          <Button size="md" className="mt-4" disabled={setup.isPending} onClick={() => setup.mutate()}>
            {setup.isPending ? "Getting ready…" : "Turn on two-step sign-in"}
          </Button>
          {setup.isError && <p className="mt-2 text-[14px] text-[#a4553f]">{errorOf(setup.error)}</p>}
          {!user.has_password && (
            <p className="mt-3 text-[13.5px] text-muted">
              Set a password first: with two-step sign-in you sign in with your email, password and code (not Google).
            </p>
          )}
        </>
      ) : (
        <>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-[15px] text-ink">
            <li>Open your authenticator app and add an account.</li>
            <li>Scan this code with it, or type the key below.</li>
            <li>Type the 6-digit code the app shows, and press Turn on.</li>
          </ol>
          <div className="mt-4 flex flex-wrap items-center gap-5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={setup.data.qr} alt="QR code for your authenticator app" className="h-44 w-44 rounded-xl border border-line bg-white p-1" />
            <div className="min-w-0">
              <p className="text-[13.5px] text-muted">Key (if you can&apos;t scan):</p>
              <p className="notranslate break-all font-mono text-[15px] font-semibold text-ink" translate="no">
                {setup.data.secret.match(/.{1,4}/g)?.join(" ")}
              </p>
              <a href={setup.data.link} className="mt-2 inline-block text-[14px] font-semibold text-sage-deep hover:underline">
                On this phone? Open in the app
              </a>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {input}
            <Button size="md" disabled={code.length !== 6 || enable.isPending} onClick={() => enable.mutate()}>
              {enable.isPending ? "Checking…" : "Turn on"}
            </Button>
          </div>
          {enable.isError && <p className="mt-2 text-[14px] text-[#a4553f]">{errorOf(enable.error)}</p>}
        </>
      )}
    </section>
  );
}
