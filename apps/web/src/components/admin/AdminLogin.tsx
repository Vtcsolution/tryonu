"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { Logo } from "@/components/ui/Logo";
import { ApiError } from "@/lib/api/client";
import { useLogin, useLogout, useSession } from "@/lib/auth/useSession";

/** where to go after signing in: a page inside the admin area only */
function adminNext(asked: string | null): string {
  return asked && asked.startsWith("/admin/dashboard") ? asked : "/admin/dashboard";
}

/** /admin/login: sign in with an admin account. Signed in already as an
 * admin, it goes straight on; signed in as someone else, it offers to sign
 * that account out first. */
export function AdminLogin() {
  const router = useRouter();
  const params = useSearchParams();
  const next = adminNext(params.get("next"));
  const { user, isLoading } = useSession();
  const login = useLogin();
  const logout = useLogout();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needCode, setNeedCode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.is_admin) router.replace(next);
  }, [user, next, router]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await login.mutateAsync({ email, password, code: needCode ? code : undefined });
      if (!res.user.is_admin) {
        await logout.mutateAsync();
        setError("That account isn't an admin account. Use the admin email and password.");
        return;
      }
      router.replace(next);
    } catch (err) {
      if (err instanceof ApiError && err.detail === "TWO_STEP_CODE_NEEDED") {
        setNeedCode(true);
        return;
      }
      setError(err instanceof ApiError ? err.detail : "Couldn't sign in. Please try again.");
    }
  };

  if (isLoading || user?.is_admin) {
    return (
      <div className="grid min-h-screen place-items-center bg-paper">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </div>
    );
  }

  return (
    <div className="grid min-h-screen place-items-center bg-paper px-5 py-10">
      <div className="w-full max-w-[400px] rounded-[24px] border border-line bg-surface p-7 shadow-lift">
        <Logo size={30} />
        <h1 className="mt-6 font-display text-[26px] text-ink">Admin sign in</h1>
        <p className="mt-1 text-[15px] text-muted">For TryOnU admins only.</p>

        {user ? (
          <div className="mt-6">
            <p className="text-[15px] text-ink">
              You&rsquo;re signed in as <b>{user.email}</b>, which isn&rsquo;t an admin account.
            </p>
            <Button
              size="md"
              className="mt-4 w-full"
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
            >
              {logout.isPending ? "Signing out…" : "Sign out and use the admin account"}
            </Button>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 space-y-4" noValidate>
            <Input label="Admin email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            <PasswordInput
              label="Password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
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
            <Button type="submit" size="md" className="w-full" disabled={login.isPending || logout.isPending}>
              {login.isPending ? "Signing in…" : "Sign in to admin"}
            </Button>
            <Link href="/forgot-password" className="inline-block text-[14px] text-sage hover:text-sage-deep">
              Forgot password?
            </Link>
          </form>
        )}
        <Link href="/" className="mt-6 block text-[14px] text-muted hover:text-ink">
          ← Back to TryOnU
        </Link>
      </div>
    </div>
  );
}
