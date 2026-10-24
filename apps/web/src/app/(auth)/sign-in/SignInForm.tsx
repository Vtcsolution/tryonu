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
  const [error, setError] = useState<string | null>(
    params.get("error") === "google" ? "Google sign-in didn't finish. Please try again." : null,
  );

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login.mutateAsync({ email, password });
      router.push(next);
      router.refresh();
    } catch (err) {
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
      subtitle="Pick up your fitting profile and looks where you left off."
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
