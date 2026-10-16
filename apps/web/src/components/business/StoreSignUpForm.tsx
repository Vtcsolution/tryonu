"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { AuthCard } from "@/components/auth/AuthCard";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { Button } from "@/components/ui/Button";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";
import { useRegister, useSession } from "@/lib/auth/useSession";

/** A store account: email, password, country. The store itself is set up next, at /business. */
export function StoreSignUpForm() {
  const router = useRouter();
  const { user, isLoading } = useSession();
  const register = useRegister();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [country, setCountry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const hint = useQuery({ queryKey: ["country-hint"], queryFn: auth.countryHint, staleTime: Infinity, retry: false });

  useEffect(() => {
    if (hint.data?.country && !country) setCountry(hint.data.country);
  }, [hint.data, country]);

  // already signed in: straight to setting up (or running) the store
  useEffect(() => {
    if (!isLoading && user) router.replace("/business");
  }, [isLoading, user, router]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.includes("@")) return setError("Please type your email address.");
    if (password.length < 8) return setError("Your password needs at least 8 characters.");
    if (!country) return setError("Please choose your country.");
    try {
      await register.mutateAsync({ email, password, country });
      router.push("/business");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't create your store account. Please try again.");
    }
  };

  return (
    <AuthCard
      kicker="For shops and brands"
      title={
        <>
          Open your store on <em>TryOnU</em>
        </>
      }
      subtitle="Shoppers try your products on their own photo before they buy. Step 1: your account."
      footer={
        <>
          Already have a store account?{" "}
          <Link href="/sign-in?next=/business" className="font-semibold text-sage hover:text-sage-deep">
            Sign in
          </Link>
          <span className="mx-2 text-faint">·</span>
          <Link href="/sign-up" className="text-muted hover:text-ink">
            Shopping, not selling?
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Input label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordInput
          label="Password (at least 8 characters)"
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
          hint="Type to search. Shoppers in this country see your products first."
        />
        {error && (
          <p role="alert" className="text-[14px] text-[#a4553f]">
            {error}
          </p>
        )}
        <Button type="submit" size="md" className="w-full" disabled={register.isPending}>
          {register.isPending ? "Creating your account…" : "Create store account"}
          {!register.isPending && <span aria-hidden="true">→</span>}
        </Button>
        <p className="text-center text-[13.5px] text-muted">Next you&apos;ll add your store name and where you deliver.</p>
      </form>
      <GoogleButton divider next="/business" />
    </AuthCard>
  );
}
