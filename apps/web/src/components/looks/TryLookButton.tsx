"use client";

import Link from "next/link";
import { useSession } from "@/lib/auth/useSession";
import { rememberReturnTo } from "@/lib/returnTo";

/**
 * "Try this look on you first": pulses and shines so nobody misses it.
 * Without an account it goes through sign-up first and remembers the look,
 * so after signing up (and the $1 first outfit) the shopper lands straight on
 * this look, ready to add their photo. The chosen look is never lost.
 */
export function TryLookButton({ lookId, size = "lg", className = "" }: { lookId: string; size?: "md" | "lg"; className?: string }) {
  const { user } = useSession();
  const target = `/looks/${lookId}/try`;
  const href = user ? target : `/sign-up?next=${encodeURIComponent(target)}`;
  return (
    <Link
      href={href}
      onClick={() => {
        if (!user) rememberReturnTo(target);
      }}
      className={`tu-press tu-attention tu-shine relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-sage font-semibold text-white hover:bg-sage-deep ${
        size === "lg" ? "min-h-[56px] px-7 text-[17.5px]" : "min-h-[46px] px-5 text-[15.5px]"
      } ${className}`}
    >
      Try this look on you first <span aria-hidden="true">→</span>
    </Link>
  );
}
