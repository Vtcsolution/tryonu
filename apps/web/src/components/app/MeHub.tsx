"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Avatar } from "@/components/community/parts";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { HelpWhatsApp } from "@/components/whatsapp/WhatsApp";
import { auth, community, notifications } from "@/lib/api/endpoints";
import { useLogout, useSession } from "@/lib/auth/useSession";

type Row = { href: string; label: string; hint?: string; badge?: ReactNode };

function Group({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div>
      <p className="px-1 text-[12.5px] font-semibold uppercase tracking-[0.12em] text-faint">{title}</p>
      <ul className="mt-2 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
        {rows.map((r) => (
          <li key={r.href + r.label}>
            <Link href={r.href} prefetch={false} className="tu-tap flex min-h-[54px] items-center gap-3 px-4 py-2.5 active:bg-paper-2">
              <span className="min-w-0 flex-1">
                <span className="block text-[16px] text-ink">{r.label}</span>
                {r.hint && <span className="block truncate text-[13px] text-muted">{r.hint}</span>}
              </span>
              {r.badge}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="shrink-0 text-faint" aria-hidden="true">
                <path d="m9 6 6 6-6 6" />
              </svg>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The "Me" tab: me, my credits, and everything else in tidy lists (the app's menu). */
export function MeHub() {
  const router = useRouter();
  const { user, isLoading } = useSession();
  const logout = useLogout();
  const me = useQuery({ queryKey: ["community", "me"], queryFn: community.me, enabled: !!user });
  const unread = useQuery({ queryKey: ["notifications", "unread"], queryFn: notifications.unread, enabled: !!user, staleTime: 0 });
  const resend = useMutation({ mutationFn: auth.resendVerification });

  if (isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;

  const count = unread.data?.unread ?? 0;
  return (
    <section className="mx-auto max-w-[620px] px-4 pb-8 pt-5">
      {user ? (
        <div className="flex items-center gap-4 rounded-[22px] border border-line bg-surface p-4">
          <Link href={me.data ? `/u/${me.data.handle}` : "/community/me"} className="shrink-0">
            <Avatar name={user.full_name ?? null} handle={user.email} url={user.avatar_url} size={64} />
          </Link>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[19px] font-semibold text-ink">{user.full_name || user.email}</p>
            {me.data && <p className="truncate text-[14px] text-muted">@{me.data.handle}</p>}
            <p className="mt-1 text-[15px] text-ink">
              <b>{user.credits_balance}</b> credits
            </p>
          </div>
          <Link href="/credits" className="tu-tap shrink-0 rounded-full bg-sage px-4 py-2.5 text-[14.5px] font-semibold text-white">
            Add credits
          </Link>
        </div>
      ) : (
        <div className="rounded-[22px] border border-line bg-surface p-5 text-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/pwa/icon-192.png" alt="" className="mx-auto h-14 w-14 rounded-2xl" />
          <p className="mt-3 text-[19px] font-semibold text-ink">Welcome to TryOnU</p>
          <p className="mt-1 text-[14.5px] text-muted">Try real clothes on your own photo before you buy.</p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Link href="/sign-in" className="tu-tap flex min-h-[48px] items-center justify-center rounded-full border border-line-strong text-[15.5px] font-semibold text-ink">
              Sign in
            </Link>
            <Link href="/sign-up" className="tu-tap flex min-h-[48px] items-center justify-center rounded-full bg-sage text-[15.5px] font-semibold text-white">
              Join free
            </Link>
          </div>
        </div>
      )}

      {user && !user.email_verified && (
        <div className="mt-4 rounded-2xl border border-[#c9a13b]/50 bg-[#c9a13b]/[0.08] p-4">
          <p className="text-[15.5px] font-semibold text-ink">Please confirm your email</p>
          <p className="mt-0.5 text-[14px] text-muted">We sent you a link. It keeps your account safe.</p>
          <button
            type="button"
            disabled={resend.isPending || resend.isSuccess}
            onClick={() => resend.mutate()}
            className="tu-tap mt-3 min-h-[42px] rounded-full border border-line-strong bg-surface px-4 text-[14.5px] font-semibold text-ink disabled:opacity-60"
          >
            {resend.isSuccess ? "Sent ✓ Check your inbox" : resend.isPending ? "Sending…" : "Send the link again"}
          </button>
        </div>
      )}

      <div className="mt-6 space-y-6">
        {user && (
          <Group
            title="My things"
            rows={[
              {
                href: "/notifications",
                label: "Notifications",
                badge: count > 0 ? <span className="rounded-full bg-[#c0503a] px-2 py-0.5 text-[12px] font-bold text-white">{count}</span> : undefined,
              },
              { href: "/saved", label: "My looks" },
              { href: "/community/saved", label: "Saved posts" },
              { href: "/alerts", label: "Price alerts" },
              { href: me.data ? `/u/${me.data.handle}` : "/community/me", label: "My profile" },
              { href: "/wardrobe", label: "My clothes" },
              { href: "/outfits", label: "Build an outfit" },
              { href: "/earn", label: "Invite & earn" },
            ]}
          />
        )}
        <Group
          title="Shop with AI"
          rows={[
            { href: "/stylist", label: "AI Stylist", hint: "Describe a look, get real products" },
            { href: "/find-look", label: "Find by photo", hint: "Upload a photo, get the products" },
            { href: "/community/challenges", label: "Style challenges", hint: "Win free credits every week" },
          ]}
        />
        {user && (
          <Group
            title="Settings"
            rows={[
              { href: "/preferences", label: "My size & style" },
              { href: "/account", label: "Settings", hint: "Name, email, password" },
              { href: "/business", label: "My store", hint: "If you sell on TryOnU" },
              { href: "/app", label: "Get the app" },
              ...(user.is_admin ? [{ href: "/admin", label: "Admin" }] : []),
            ]}
          />
        )}
        <HelpWhatsApp variant="row" />
        <div className="flex min-h-[54px] items-center justify-between rounded-2xl border border-line bg-surface px-4">
          <span className="text-[16px] text-ink">Light or dark look</span>
          <ThemeToggle />
        </div>
        {user && (
          <button
            type="button"
            onClick={async () => {
              await logout.mutateAsync();
              router.push("/");
              router.refresh();
            }}
            className="tu-tap min-h-[52px] w-full rounded-2xl border border-line bg-surface text-[16px] font-semibold text-[#a4553f]"
          >
            Sign out
          </button>
        )}
        <p className="pt-2 text-center text-[13px] text-faint">Help, prices, business and legal pages: tap ☰ at the top.</p>
      </div>
    </section>
  );
}
