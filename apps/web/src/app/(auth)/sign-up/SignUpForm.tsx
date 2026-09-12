"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AuthCard } from "@/components/auth/AuthCard";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";
import { useRegister } from "@/lib/auth/useSession";

export function SignUpForm() {
  const params = useSearchParams();
  const next = params.get("next") || "/try";
  const register = useRegister();
  const resend = useMutation({ mutationFn: auth.resendVerification });

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [registered, setRegistered] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await register.mutateAsync({ email, password, full_name: fullName || undefined });
      setRegistered(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't create your account. Please try again.");
    }
  };

  if (registered) {
    return (
      <AuthCard
        kicker="Try it. See you. Shop it."
        title={
          <>
            Check your <em>email</em>
          </>
        }
        subtitle={`We sent a verification link to ${email}. Verify it to unlock your 100 free credits.`}
      >
        <div className="space-y-3">
          <Button href={next} size="md" className="w-full">
            Continue to TryOnU <span aria-hidden="true">→</span>
          </Button>
          <Button
            variant="outline"
            size="md"
            className="w-full"
            disabled={resend.isPending || resend.isSuccess}
            onClick={() => resend.mutate()}
          >
            {resend.isSuccess ? "Email resent" : resend.isPending ? "Resending…" : "Resend verification email"}
          </Button>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      kicker="Try it. See you. Shop it."
      title={
        <>
          Create your <em>fitting profile</em>
        </>
      }
      subtitle="100 free credits — verify your email to unlock them."
      footer={
        <>
          Already have an account?{" "}
          <Link href={`/sign-in${next ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-semibold text-sage hover:text-sage-deep">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input
          label="Full name"
          type="text"
          autoComplete="name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
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

        <Button type="submit" size="md" className="w-full" disabled={register.isPending}>
          {register.isPending ? "Creating account…" : "Create account"}
          {!register.isPending && <span aria-hidden="true">→</span>}
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
