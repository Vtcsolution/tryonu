"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Avatar } from "@/components/community/parts";
import { LensIcon } from "@/components/lens/LensIcon";
import { useSession } from "@/lib/auth/useSession";

type Tab = { id: string; label: string; href: string; icon: (on: boolean) => ReactNode; match: (p: string) => boolean };

const ME_PAGES = ["/me", "/saved", "/alerts", "/notifications", "/account", "/preferences", "/credits", "/app", "/stylist"];

/** On phones (the website and the installed app): the app's tabs at the bottom. */
export function AppTabBar() {
  const pathname = usePathname() || "/";
  const { user } = useSession();
  const tabs: Tab[] = [
    {
      id: "home",
      label: "Home",
      href: user ? "/for-you" : "/",
      icon: (on) => (
        <svg width="24" height="24" viewBox="0 0 24 24" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
          <path d="M3.5 10.5 12 3.5l8.5 7V20a1 1 0 0 1-1 1h-5v-6h-5v6h-5a1 1 0 0 1-1-1z" />
        </svg>
      ),
      match: (p) => p === "/" || p.startsWith("/for-you"),
    },
    {
      id: "try",
      label: "Try on",
      href: "/try",
      icon: (on) => (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={on ? 2.4 : 1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 7.5a2 2 0 1 1 2-2" />
          <path d="M12 7.5v1.6L3.4 15.2a1.4 1.4 0 0 0 .8 2.5h15.6a1.4 1.4 0 0 0 .8-2.5L12 9.1" />
        </svg>
      ),
      match: (p) => p.startsWith("/try") || p.startsWith("/outfits") || p.startsWith("/wardrobe"),
    },
    {
      id: "find",
      label: "Find",
      href: "/find-look",
      icon: () => <LensIcon size={26} />,
      match: (p) => p.startsWith("/find-look"),
    },
    {
      id: "community",
      label: "Community",
      href: "/community",
      icon: (on) => (
        <svg width="24" height="24" viewBox="0 0 24 24" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="9" cy="8" r="3.5" />
          <path d="M2.5 20c.6-3.5 3.3-5.5 6.5-5.5s5.9 2 6.5 5.5z" />
          <path d="M16 4.8a3.3 3.3 0 0 1 0 6.4M18.5 14.7c1.6.8 2.7 2.6 3 5.3" fill="none" />
        </svg>
      ),
      match: (p) => p.startsWith("/community") || p.startsWith("/u/"),
    },
    {
      id: "me",
      label: "Me",
      href: "/me",
      icon: (on) =>
        user ? (
          <span className={`rounded-full ${on ? "ring-2 ring-sage-deep ring-offset-2 ring-offset-surface" : ""}`}>
            <Avatar name={user.full_name ?? null} handle={user.email} url={user.avatar_url} size={24} />
          </span>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 21a8 8 0 0 1 16 0z" />
          </svg>
        ),
      match: (p) => ME_PAGES.some((m) => p === m || p.startsWith(`${m}/`)),
    },
  ];

  return (
    <nav
      aria-label="App"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
    >
      <ul className="mx-auto grid h-16 max-w-[560px] grid-cols-5">
        {tabs.map((t) => {
          const on = t.match(pathname);
          if (t.id === "find") {
            return (
              <li key={t.id} className="flex justify-center">
                <Link href={t.href} aria-current={on ? "page" : undefined} className="tu-tap -mt-5 flex flex-col items-center gap-1">
                  <span
                    className={`grid h-[54px] w-[54px] place-items-center rounded-full text-white shadow-lift ring-4 ring-surface transition-colors ${
                      on ? "bg-sage-deep" : "bg-sage"
                    }`}
                  >
                    {t.icon(on)}
                  </span>
                  <span className={`text-[11px] font-semibold ${on ? "text-sage-deep" : "text-muted"}`}>{t.label}</span>
                </Link>
              </li>
            );
          }
          return (
            <li key={t.id}>
              <Link
                href={t.href}
                aria-current={on ? "page" : undefined}
                className={`tu-tap flex h-full flex-col items-center justify-center gap-1 transition-colors ${on ? "text-sage-deep" : "text-muted"}`}
              >
                {t.icon(on)}
                <span className={`text-[11px] ${on ? "font-bold" : "font-semibold"}`}>{t.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
