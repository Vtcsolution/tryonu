"use client";

import Link from "next/link";
import { resolveMediaUrl } from "@/lib/api/client";
import { usePathname, useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { auth } from "@/lib/api/endpoints";
import { useLogout, useSession } from "@/lib/auth/useSession";

export function AccountMenu() {
  const { user, isLoading } = useSession();
  const logout = useLogout();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const resend = useMutation({ mutationFn: auth.resendVerification });
  const box = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  // closes on a click or tap anywhere else, on Escape, and on going to another page.
  // (A full-page layer behind it didn't work: the header's blur keeps such a
  // layer inside the header, so clicks on the page never reached it.)
  useEffect(() => {
    if (!open) return;
    const outside = (e: PointerEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  useEffect(() => setOpen(false), [pathname]);

  if (isLoading) {
    return <div className="h-9 w-[110px] animate-pulse rounded-full bg-ink/[0.06]" />;
  }

  if (!user) {
    return (
      <Link
        href="/sign-in"
        className="group/si relative hidden whitespace-nowrap font-display text-[16px] tracking-[-0.01em] text-ink transition-colors duration-200 sm:inline-block"
      >
        Sign in
        <span className="absolute -bottom-1 left-0 h-px w-full origin-left scale-x-0 bg-ink transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover/si:scale-x-100" />
      </Link>
    );
  }

  const initial = (user.full_name || user.email)[0]?.toUpperCase();

  return (
    <div ref={box} className="group relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2.5 rounded-full border border-line py-1 pl-1 pr-3 transition-colors hover:border-line-strong"
      >
        {user.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={resolveMediaUrl(user.avatar_url)} alt="" className="h-7 w-7 rounded-full object-cover" />
        ) : (
          <span className="grid h-7 w-7 place-items-center rounded-full bg-sage text-[13px] font-semibold text-white">
            {initial}
          </span>
        )}
        {/* The balance, verified or not — the red dot below is what asks
            for verification, and replacing the number with "Verify email"
            left shoppers unable to see credits they actually hold. */}
        <span className="hidden font-display text-[14px] text-ink sm:inline">
          {user.credits_balance} credits
        </span>
        {!user.email_verified && (
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#c0503a]" aria-hidden="true" />
        )}
      </button>

      <div
        className={`absolute right-0 top-full z-50 pt-3 transition-[opacity,transform] duration-200 ${
          open ? "visible translate-y-0 opacity-100" : "invisible -translate-y-1 opacity-0"
        }`}
      >
        <div className="w-[220px] rounded-2xl border border-line bg-surface p-2 shadow-lift">
          <div className="px-3 py-2">
            <p className="truncate text-[14px] font-semibold text-ink">
              {user.full_name || user.email}
            </p>
            {/* The real balance either way. This used to print "0 credits"
                for an unverified account, which was simply untrue — the
                credits are there and nothing stops them being spent, so a
                shopper with 200 was told they had none. */}
            <p className="text-[13px] text-muted">
              {user.credits_balance} credits{user.email_verified ? "" : " · email unverified"}
            </p>
          </div>
          {!user.email_verified && (
            <button
              type="button"
              disabled={resend.isPending || resend.isSuccess}
              onClick={() => resend.mutate()}
              className="block w-full rounded-xl px-3 py-2 text-left text-[14px] text-sage-deep transition-colors hover:bg-paper-2 disabled:opacity-60"
            >
              {resend.isSuccess ? "Verification email sent" : resend.isPending ? "Sending…" : "Resend verification email"}
            </button>
          )}
          {[
            { href: "/gallery", label: "My looks" },
            { href: "/saved", label: "Saved looks" },
            { href: "/notifications", label: "Notifications" },
            { href: "/alerts", label: "Price alerts" },
            { href: "/community/me", label: "My profile" },
            { href: "/preferences", label: "My size & style" },
            { href: "/credits", label: "Buy credits" },
            { href: "/earn", label: "Invite & earn" },
            { href: "/account", label: "Settings" },
            ...(user.is_admin || user.is_team ? [{ href: "/team", label: "Team panel" }] : []),
            ...(user.is_admin ? [{ href: "/admin/dashboard", label: "Admin" }] : []),
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              prefetch={false}
              onClick={() => setOpen(false)}
              className="block rounded-xl px-3 py-2 text-[14px] text-ink-soft transition-colors hover:bg-paper-2"
            >
              {item.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={async () => {
              setOpen(false);
              await logout.mutateAsync();
              router.push("/");
              router.refresh();
            }}
            className="block w-full rounded-xl px-3 py-2 text-left text-[14px] text-ink-soft transition-colors hover:bg-paper-2"
          >
            Sign out
          </button>
        </div>
      </div>

    </div>
  );
}
