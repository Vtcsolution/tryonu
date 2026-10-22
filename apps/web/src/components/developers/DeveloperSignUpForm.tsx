"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { Button } from "@/components/ui/Button";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";
import { useRegister, useSession } from "@/lib/auth/useSession";

/** A developer account: email, password, country. The developer account is named next, at /developers. */
export function DeveloperSignUpForm() {
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

  // already signed in: straight to the developer portal
  useEffect(() => {
    if (!isLoading && user) router.replace("/developers/console");
  }, [isLoading, user, router]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.includes("@")) return setError("Please type your email address.");
    if (password.length < 8) return setError("Your password needs at least 8 characters.");
    if (!country) return setError("Please choose your country.");
    try {
      await register.mutateAsync({ email, password, country });
      router.push("/developers/console");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't create your developer account. Please try again.");
    }
  };

  return (
    <div className="rounded-2xl border border-line bg-surface p-6 shadow-lift sm:p-8">
      <p className="text-[20px] font-semibold text-ink">Create your developer account</p>
      <p className="mt-1 text-[14.5px] text-muted">Step 1 of 3: your sign-in. Next, name your project and get a key.</p>
      <div className="mt-6">
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
          hint="Type to search."
        />
        {error && (
          <p role="alert" className="text-[14px] text-[#a4553f]">
            {error}
          </p>
        )}
        <Button type="submit" size="md" className="w-full" disabled={register.isPending}>
          {register.isPending ? "Creating your account…" : "Create developer account"}
          {!register.isPending && <span aria-hidden="true">→</span>}
        </Button>
        <p className="text-center text-[13.5px] text-muted">Next: name your project, create an API key and buy credits.</p>
      </form>
      <GoogleButton divider next="/developers/console" />
      </div>
      <p className="mt-6 text-center text-[14px] text-muted">
          Already have an account?{" "}
          <Link href="/sign-in?next=/developers/console" className="font-semibold text-sage hover:text-sage-deep">
            Sign in
          </Link>
          <span className="mx-2 text-faint">·</span>
          <Link href="/sign-up" className="text-muted hover:text-ink">
            Just shopping?
          </Link>
      </p>
    </div>
  );
}
