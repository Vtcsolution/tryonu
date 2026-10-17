"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { BUSINESS, COMPANY, PRODUCT, TOP_LINKS } from "@/components/marketing/navLinks";
import { useSession } from "@/lib/auth/useSession";

/** Phones and small screens: the whole site menu behind one button. */
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
        className="grid h-11 w-11 place-items-center rounded-full border border-line text-ink hover:border-line-strong xl:hidden"
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
                {[PRODUCT, BUSINESS, COMPANY].map((g) => (
                  <div key={g.label}>
                    <p className="text-[12.5px] font-semibold uppercase tracking-[0.12em] text-faint">{g.label}</p>
                    <ul className="mt-2">
                      {g.items.map((l) => (
                        <li key={l.href}>
                          <Link href={l.href} prefetch={false} className="block rounded-lg py-2.5 text-[16.5px] text-ink hover:text-sage-deep">
                            {l.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <ul className="border-t border-line pt-4">
                  {TOP_LINKS.map((l) => (
                    <li key={l.href}>
                      <Link href={l.href} prefetch={false} className="block py-2.5 text-[16.5px] text-ink hover:text-sage-deep">
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
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
