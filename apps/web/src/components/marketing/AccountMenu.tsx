"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useLogout, useSession } from "@/lib/auth/useSession";

export function AccountMenu() {
  const { user, isLoading } = useSession();
  const logout = useLogout();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  if (isLoading) {
    return <div className="h-9 w-[110px] animate-pulse rounded-full bg-ink/[0.06]" />;
  }

  if (!user) {
    return (
      <Link
        href="/sign-in"
        className="group/si relative hidden font-display text-[15px] tracking-[-0.01em] text-ink transition-colors duration-200 sm:inline-block"
      >
        Sign in
        <span className="absolute -bottom-1 left-0 h-px w-full origin-left scale-x-0 bg-ink transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover/si:scale-x-100" />
      </Link>
    );
  }

  const initial = (user.full_name || user.email)[0]?.toUpperCase();

  return (
    <div className="group relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2.5 rounded-full border border-line py-1 pl-1 pr-3 transition-colors hover:border-line-strong"
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-sage text-[12px] font-semibold text-white">
          {initial}
        </span>
        <span className="hidden font-display text-[13px] text-ink sm:inline">
          {user.credits_balance} credits
        </span>
      </button>

      <div
        className={`absolute right-0 top-full z-50 pt-3 transition-[opacity,transform] duration-200 ${
          open ? "visible translate-y-0 opacity-100" : "invisible -translate-y-1 opacity-0"
        }`}
      >
        <div className="w-[200px] rounded-2xl border border-line bg-surface p-2 shadow-lift">
          <div className="px-3 py-2">
            <p className="truncate text-[13px] font-semibold text-ink">
              {user.full_name || user.email}
            </p>
            <p className="text-[12px] text-muted">{user.credits_balance} credits</p>
          </div>
          <Link
            href="/try"
            onClick={() => setOpen(false)}
            className="block rounded-xl px-3 py-2 text-[13px] text-ink-soft transition-colors hover:bg-paper-2"
          >
            Try-on studio
          </Link>
          <button
            type="button"
            onClick={async () => {
              setOpen(false);
              await logout.mutateAsync();
              router.push("/");
              router.refresh();
            }}
            className="block w-full rounded-xl px-3 py-2 text-left text-[13px] text-ink-soft transition-colors hover:bg-paper-2"
          >
            Sign out
          </button>
        </div>
      </div>

      {open && (
        <button
          type="button"
          aria-hidden="true"
          tabIndex={-1}
          className="fixed inset-0 z-40 cursor-default"
          onClick={() => setOpen(false)}
        />
      )}
    </div>
  );
}
