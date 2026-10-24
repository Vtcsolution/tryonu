"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { AuthCard } from "@/components/auth/AuthCard";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";
import { useRegister } from "@/lib/auth/useSession";
import { safePath, usePendingReturnTo } from "@/lib/returnTo";

export function SignUpForm() {
  const params = useSearchParams();
  const pending = usePendingReturnTo();
  const asked = params.get("next");
  const wanted = (safePath(asked) ? asked : null) || pending;
  const next = wanted || "/try";
  const register = useRegister();
  const resend = useMutation({ mutationFn: auth.resendVerification });

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [country, setCountry] = useState("");
  const [error, setError] = useState<string | null>(null);
  // pre-filled from where they are; they can pick any country
  const hint = useQuery({ queryKey: ["country-hint"], queryFn: auth.countryHint, staleTime: Infinity, retry: false });
  useEffect(() => {
    if (hint.data?.country && !country) setCountry(hint.data.country);
  }, [hint.data, country]);
  const [registered, setRegistered] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!country) {
      setError("Please choose your country.");
      return;
    }
    try {
      await register.mutateAsync({ email, password, full_name: fullName || undefined, country, next: wanted || undefined });
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
        subtitle={`Your account is ready. We also sent a verification link to ${email}; verify when you get a chance.`}
      >
        <div className="space-y-3">
          <Button href={`/preferences?next=${encodeURIComponent(wanted || "/for-you")}`} size="md" className="w-full">
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
      subtitle="See every outfit on your own photo before you buy."
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
        <PasswordInput
          label="Password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <CountryPicker
          label="Your country"
          value={country}
          onChange={setCountry}
          suggested={hint.data?.country}
          hint="Type to search. We show you shops that deliver to your country."
        />

        {error && (
          <p role="alert" className="text-[14px] text-[#a4553f]">
            {error}
          </p>
        )}

        <Button type="submit" size="md" className="w-full" disabled={register.isPending}>
          {register.isPending ? "Creating account…" : "Create account"}
          {!register.isPending && <span aria-hidden="true">→</span>}
        </Button>
      </form>

      <GoogleButton divider next={next} />
    </AuthCard>
  );
}
