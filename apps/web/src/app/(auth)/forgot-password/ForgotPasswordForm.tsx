"use client";

import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AuthCard } from "@/components/auth/AuthCard";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const request = useMutation({ mutationFn: auth.forgotPassword });

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await request.mutateAsync({ email });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't send the reset link. Please try again.");
    }
  };

  return (
    <AuthCard
      kicker="Account recovery"
      title={
        <>
          Reset your <em>password</em>
        </>
      }
      subtitle="We'll email you a link to choose a new one."
      footer={
        <>
          Remembered it?{" "}
          <Link href="/sign-in" className="font-semibold text-sage hover:text-sage-deep">
            Sign in
          </Link>
        </>
      }
    >
      {sent ? (
        <p className="text-[14px] leading-relaxed text-ink-soft">
          If an account exists for <span className="font-semibold text-ink">{email}</span>, a reset
          link is on its way. Check your inbox — the link expires in 30 minutes.
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          {error && (
            <p role="alert" className="text-[13px] text-[#a4553f]">
              {error}
            </p>
          )}

          <Button type="submit" size="md" className="w-full" disabled={request.isPending}>
            {request.isPending ? "Sending…" : "Send reset link"}
            {!request.isPending && <span aria-hidden="true">→</span>}
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
