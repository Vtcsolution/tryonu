"use client";

import Link from "next/link";
import { useSession } from "@/lib/auth/useSession";

/** Phones' top bar, right side: my credits (or "Sign in"); everything else lives in the Me tab. */
export function PhoneAccount() {
  const { user, isLoading } = useSession();
  if (isLoading) return <span className="h-8 w-16 animate-pulse rounded-full bg-ink/[0.06] lg:hidden" />;
  if (!user) {
    return (
      <Link href="/sign-in" className="tu-tap rounded-full bg-sage px-4 py-2 text-[14px] font-semibold text-white lg:hidden">
        Sign in
      </Link>
    );
  }
  return (
    <Link
      href="/credits"
      title="Your credits"
      className="tu-tap flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-[13.5px] font-semibold text-ink lg:hidden"
    >
      <span className="h-2 w-2 rounded-full bg-sage" aria-hidden="true" />
      {user.credits_balance}
      <span className="sr-only">credits</span>
    </Link>
  );
}
