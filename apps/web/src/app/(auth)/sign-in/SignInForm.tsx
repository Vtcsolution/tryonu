"use client";

import { safePath, usePendingReturnTo } from "@/lib/returnTo";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { AuthCard } from "@/components/auth/AuthCard";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { ApiError } from "@/lib/api/client";
import { useLogin } from "@/lib/auth/useSession";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const pending = usePendingReturnTo();
  const asked = params.get("next");
  const next = (safePath(asked) ? asked : null) || pending || "/try";
  const login = useLogin();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needCode, setNeedCode] = useState(false);
  const [error, setError] = useState<string | null>(
    params.get("error") === "google"
      ? "Google sign-in didn't finish. Please try again."
      : params.get("error") === "two_step"
        ? "This account uses two-step sign-in: sign in with your email, password and the code from your app."
        : null,
  );

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login.mutateAsync({ email, password, code: needCode ? code : undefined });
      router.push(next);
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && err.detail === "TWO_STEP_CODE_NEEDED") {
        setNeedCode(true);
        return;
      }
      setError(err instanceof ApiError ? err.detail : "Couldn't sign in. Please try again.");
    }
  };

  return (
    <AuthCard
      kicker="Welcome back"
      title={
        <>
          Sign in to <em>TryOnU</em>
        </>
      }
      subtitle="Your photo and your looks are waiting for you."
      footer={
        <>
          New here?{" "}
          <Link href={`/sign-up${next ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-semibold text-sage hover:text-sage-deep">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <div>
          <PasswordInput
            label="Password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Link
            href="/forgot-password"
            className="mt-1.5 inline-block text-[14px] text-sage hover:text-sage-deep"
          >
            Forgot password?
          </Link>
        </div>

        {needCode && (
          <div>
            <label htmlFor="two-step-code" className="block text-[14.5px] font-medium text-ink">
              6-digit code from your authenticator app
            </label>
            <input
              id="two-step-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="123456"
              className="mt-1.5 h-12 w-full rounded-xl border border-line-strong bg-paper px-3.5 text-center text-[20px] tracking-[0.3em] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25"
            />
          </div>
        )}
        {error && (
          <p role="alert" className="text-[14px] text-[#a4553f]">
            {error}
          </p>
        )}

        <Button type="submit" size="md" className="w-full" disabled={login.isPending}>
          {login.isPending ? "Signing in…" : "Sign in"}
          {!login.isPending && <span aria-hidden="true">→</span>}
        </Button>
      </form>

      <GoogleButton divider next={next} />
    </AuthCard>
  );
}
