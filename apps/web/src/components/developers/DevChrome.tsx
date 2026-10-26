"use client";

import { copyrightLine } from "@/lib/seo";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { useSession } from "@/lib/auth/useSession";

// the developer portal's own menu: nothing from the shopping site
export const DEV_NAV: { label: string; href: string }[] = [
  { label: "Overview", href: "/developers" },
  { label: "Docs", href: "/developers/docs" },
  { label: "API reference", href: "/developers/docs#reference" },
  { label: "Plugins", href: "/developers/docs#widget" },
  { label: "Pricing", href: "/developers#pricing" },
];

const FOOTER: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
  {
    title: "Build",
    links: [
      { label: "Quick start", href: "/developers/docs#how-it-works" },
      { label: "Server API", href: "/developers/docs#code" },
      { label: "API reference", href: "/developers/docs#reference" },
      { label: "Website widget", href: "/developers/docs#widget" },
    ],
  },
  {
    title: "Account",
    links: [
      { label: "Create an account", href: "/developers/sign-up" },
      { label: "Console", href: "/developers/console" },
      { label: "API keys", href: "/developers/console#keys" },
      { label: "Buy credits", href: "/developers/console#credits" },
    ],
  },
  {
    title: "Help",
    links: [
      { label: "Contact developer support", href: "/contact" },
      { label: "Pricing", href: "/developers#pricing" },
      { label: "Terms", href: "/terms" },
      { label: "Privacy", href: "/privacy" },
    ],
  },
];

function active(pathname: string, href: string) {
  const path = href.split("#")[0];
  if (href.includes("#")) return false;
  return path === "/developers" ? pathname === "/developers" : pathname.startsWith(path);
}

function DevMark({ dark = true }: { dark?: boolean }) {
  return (
    <Link href="/developers" className="flex items-center gap-2.5" aria-label="TryOnU Developers: home">
      <Logo size={28} href="" tone={dark ? "light" : "ink"} />
      <span className="rounded-md border border-[#7d917a]/50 bg-[#7d917a]/15 px-2 py-0.5 font-mono text-[12px] font-semibold uppercase tracking-[0.08em] text-[#b9cdb5]">
        Developers
      </span>
    </Link>
  );
}

/** The developer portal's header: its own logo, menu and account buttons, dark like a console. */
export function DevHeader() {
  const pathname = usePathname() || "/developers";
  const { user } = useSession();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [pathname]);

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#0d1210]/95 text-white backdrop-blur">
      <div className="mx-auto flex h-16 w-[min(1280px,calc(100%-32px))] items-center gap-6">
        <DevMark />
        <nav aria-label="Developers" className="hidden flex-1 items-center gap-1 lg:flex">
          {DEV_NAV.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-lg px-3 py-2 text-[14.5px] transition-colors ${
                active(pathname, l.href) ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto hidden items-center gap-2 lg:flex">
          {user ? (
            <Link href="/developers/console" className="tu-press rounded-lg bg-[#7d917a] px-4 py-2 text-[14.5px] font-semibold text-[#0d1210] hover:bg-[#93a88f]">
              Console →
            </Link>
          ) : (
            <>
              <Link href="/sign-in?next=/developers/console" className="rounded-lg px-3 py-2 text-[14.5px] text-white/80 hover:text-white">
                Sign in
              </Link>
              <Link href="/developers/sign-up" className="tu-press rounded-lg bg-[#7d917a] px-4 py-2 text-[14.5px] font-semibold text-[#0d1210] hover:bg-[#93a88f]">
                Get API key
              </Link>
            </>
          )}
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? "Close the menu" : "Open the menu"}
          className="ml-auto grid h-10 w-10 place-items-center rounded-lg border border-white/15 lg:hidden"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            {open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>
      {open && (
        <div className="border-t border-white/10 px-4 pb-5 pt-2 lg:hidden">
          <nav aria-label="Developers" className="flex flex-col">
            {DEV_NAV.map((l) => (
              <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="border-b border-white/5 py-3.5 text-[16px] text-white/90">
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="mt-4 grid grid-cols-2 gap-2">
            {user ? (
              <Link href="/developers/console" className="col-span-2 rounded-lg bg-[#7d917a] py-3 text-center text-[15.5px] font-semibold text-[#0d1210]">
                Open the console →
              </Link>
            ) : (
              <>
                <Link href="/sign-in?next=/developers/console" className="rounded-lg border border-white/20 py-3 text-center text-[15.5px] text-white">
                  Sign in
                </Link>
                <Link href="/developers/sign-up" className="rounded-lg bg-[#7d917a] py-3 text-center text-[15.5px] font-semibold text-[#0d1210]">
                  Get API key
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

export function DevFooter() {
  return (
    <footer className="bg-[#0d1210] text-white/70">
      <div className="mx-auto grid w-[min(1280px,calc(100%-32px))] gap-10 py-14 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <DevMark />
          <p className="mt-4 max-w-xs text-[14.5px] leading-relaxed">
            AI virtual try-on for your shop or app. One REST API, a no-code website widget, and plugins.
          </p>
          <a href="/" target="_blank" rel="noopener" className="mt-5 inline-block text-[14px] font-semibold text-[#b9cdb5] hover:text-white">
            TryOnU for shoppers ↗
          </a>
        </div>
        {FOOTER.map((col) => (
          <div key={col.title}>
            <p className="font-mono text-[12px] font-semibold uppercase tracking-[0.12em] text-white/45">{col.title}</p>
            <ul className="mt-4 space-y-2.5 text-[14.5px]">
              {col.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="hover:text-white">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex w-[min(1280px,calc(100%-32px))] flex-wrap items-center justify-between gap-3 py-5 text-[13px] text-white/45">
          <span>{copyrightLine()}</span>
          <span className="flex items-center gap-2">
            Light or dark <ThemeToggle />
          </span>
        </div>
      </div>
    </footer>
  );
}

/** Every developer page: the portal's own header and footer, no shopping menus or phone tabs. */
export function DevChrome({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <DevHeader />
      <main className="tu-enter flex-1">{children}</main>
      <DevFooter />
    </div>
  );
}
