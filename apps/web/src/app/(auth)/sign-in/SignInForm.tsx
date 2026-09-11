"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AuthCard } from "@/components/auth/AuthCard";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { ApiError } from "@/lib/api/client";
import { useLogin } from "@/lib/auth/useSession";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/try";
  const login = useLogin();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

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
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && (
          <p role="alert" className="text-[13px] text-[#a4553f]">
            {error}
          </p>
        )}

        <Button type="submit" size="md" className="w-full" disabled={login.isPending}>
          {login.isPending ? "Signing in…" : "Sign in"}
          {!login.isPending && <span aria-hidden="true">→</span>}
        </Button>
      </form>

      <div className="my-5 flex items-center gap-3 text-[12px] text-faint">
        <span className="h-px flex-1 bg-line" />
        or
        <span className="h-px flex-1 bg-line" />
      </div>

      <GoogleButton />
    </AuthCard>
  );
}
