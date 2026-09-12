"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AuthCard } from "@/components/auth/AuthCard";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";

export function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");

  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const reset = useMutation({ mutationFn: auth.resetPassword });

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!token) {
      setError("This reset link is missing its token — request a new one.");
      return;
    }
    try {
      await reset.mutateAsync({ token, new_password: password });
      setDone(true);
      setTimeout(() => router.push("/sign-in"), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't reset your password. The link may have expired.");
    }
  };

  if (!token) {
    return (
      <AuthCard kicker="Account recovery" title={<>Link is invalid</>}>
        <p className="text-[14px] leading-relaxed text-ink-soft">
          This password reset link is missing or malformed.{" "}
          <Link href="/forgot-password" className="font-semibold text-sage hover:text-sage-deep">
            Request a new one
          </Link>
          .
        </p>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      kicker="Account recovery"
      title={
        <>
          Choose a <em>new password</em>
        </>
      }
      subtitle="You'll be signed out everywhere else once it's changed."
      footer={
        <>
          <Link href="/sign-in" className="font-semibold text-sage hover:text-sage-deep">
            Back to sign in
          </Link>
        </>
      }
    >
      {done ? (
        <p className="text-[14px] leading-relaxed text-ink-soft">
          Password updated. Taking you to sign in…
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && (
            <p role="alert" className="text-[13px] text-[#a4553f]">
              {error}
            </p>
          )}

          <Button type="submit" size="md" className="w-full" disabled={reset.isPending}>
            {reset.isPending ? "Updating…" : "Update password"}
            {!reset.isPending && <span aria-hidden="true">→</span>}
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
