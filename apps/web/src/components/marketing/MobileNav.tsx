"use client";

import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import { isDevPortal } from "@/lib/devLinks";
import Link from "next/link";
import { SocialLinks } from "@/components/marketing/SocialLinks";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { GROUPS, LEGAL } from "@/components/marketing/navLinks";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { copyrightLine } from "@/lib/seo";
import { useSession } from "@/lib/auth/useSession";

// a member's own pages: in the "Me" tab, not in the website menu
const MINE = ["/wardrobe", "/business"];

/** Phones and small screens: the website's pages (product, business, help, legal) behind ☰.
 * A member's own pages live in the "Me" tab on phones. */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { user } = useSession();

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open menu"
        aria-expanded={open}
        className="tu-tap grid h-10 w-10 place-items-center rounded-full text-ink active:bg-paper-2 lg:h-11 lg:w-11 lg:border lg:border-line lg:hover:border-line-strong xl:hidden"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>
      {open &&
        createPortal(
          <div className="fixed inset-0 z-[100] xl:hidden" role="dialog" aria-modal="true" aria-label="Menu">
            <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
            <nav className="absolute inset-y-0 right-0 flex w-[min(380px,100%)] flex-col overflow-y-auto bg-surface shadow-lift">
              <div className="flex items-center justify-between border-b border-line px-5 py-4">
                <span className="text-[17px] font-semibold text-ink">Menu</span>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close menu"
                  className="grid h-10 w-10 place-items-center rounded-lg text-muted hover:bg-paper-2 hover:text-ink"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                    <path d="M6 6l12 12M18 6 6 18" />
                  </svg>
                </button>
              </div>
              <div className="flex-1 space-y-6 px-5 py-5">
                <Link
                  href="/app"
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-3 rounded-2xl border border-sage/40 bg-sage-tint/30 p-3"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src="/pwa/icon-192.png" alt="" className="h-11 w-11 rounded-xl" />
                  <span className="min-w-0">
                    <span className="block text-[16px] font-semibold text-ink">Get the TryOnU app</span>
                    <span className="block text-[13.5px] text-muted">On your home screen, free, no app store</span>
                  </span>
                </Link>
                <SocialLinks label="Follow TryOnU" />
                {GROUPS.map((g) => (
                  <div key={g.label}>
                    <p className="text-[12.5px] font-semibold uppercase tracking-[0.12em] text-faint">{g.label}</p>
                    <ul className="mt-2">
                      {g.items.filter((l) => !MINE.includes(l.href)).map((l) => (
                        <li key={l.href}>
                          <Link
                            href={l.href}
                            prefetch={false}
                            className={
                              l.highlight
                                ? "my-1 inline-block py-2 text-[16.5px] text-sage-deep tu-glow-link"
                                : "block rounded-lg py-2.5 text-[16.5px] text-ink hover:text-sage-deep"
                            }
                            {...(isDevPortal(l.href) ? { target: "_blank", rel: "noopener" } : {})}
                          >
                            {l.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div>
                  <p className="text-[12.5px] font-semibold uppercase tracking-[0.12em] text-faint">Legal</p>
                  <ul className="mt-2">
                    {LEGAL.map((l) => (
                      <li key={l.href}>
                        <Link
                            href={l.href}
                            prefetch={false}
                            className="block rounded-lg py-2.5 text-[16.5px] text-ink hover:text-sage-deep"
                            {...(isDevPortal(l.href) ? { target: "_blank", rel: "noopener" } : {})}
                          >
                          {l.label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-[13px] text-muted">{copyrightLine()}</p>
                </div>
                <div className="flex items-center justify-between border-t border-line pt-4">
                  <span className="text-[16.5px] text-ink">Light or dark look</span>
                  <ThemeToggle />
                </div>
              </div>
              <div className="space-y-3 border-t border-line p-5">
                {!user && (
                  <div className="grid grid-cols-2 gap-3">
                    <Link
                      href="/sign-in"
                      className="flex min-h-[48px] items-center justify-center rounded-full border border-line-strong text-[15.5px] font-semibold text-ink"
                    >
                      Sign in
                    </Link>
                    <Link
                      href="/sign-up"
                      className="flex min-h-[48px] items-center justify-center rounded-full border border-line-strong text-[15.5px] font-semibold text-ink"
                    >
                      Create account
                    </Link>
                  </div>
                )}
                <FirstOutfitOffer className="w-full" />
                <Link
                  href="/try"
                  className="flex min-h-[50px] items-center justify-center rounded-full bg-sage text-[16px] font-semibold text-white hover:bg-sage-deep"
                >
                  Try it now →
                </Link>
              </div>
            </nav>
          </div>,
          document.body,
        )}
    </>
  );
}
