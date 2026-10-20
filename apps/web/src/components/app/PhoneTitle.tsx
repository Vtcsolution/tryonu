"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/ui/Logo";

// the app's main tabs show the logo; every other screen shows "← its name"
const ROOTS = ["/", "/for-you", "/try", "/find-look", "/community", "/me"];

// screen names, most specific first
const TITLES: [string, string][] = [
  ["/community/challenges/", "Challenge"],
  ["/community/challenges", "Style challenges"],
  ["/community/post/", "Post"],
  ["/community/saved", "Saved posts"],
  ["/community/me", "My profile"],
  ["/u/", "Profile"],
  ["/saved/", "Saved look"],
  ["/saved", "Saved looks"],
  ["/alerts", "Price alerts"],
  ["/notifications", "Notifications"],
  ["/account", "My account"],
  ["/preferences", "My style & size"],
  ["/credits", "Credits"],
  ["/stylist", "AI Stylist"],
  ["/outfits", "Outfit builder"],
  ["/wardrobe", "My wardrobe"],
  ["/app", "Get the app"],
  ["/look/", "Shared look"],
  ["/stores/", "Store"],
  ["/pricing", "Pricing"],
  ["/how-it-works", "How it works"],
  ["/faq", "Questions & answers"],
  ["/about", "About TryOnU"],
  ["/contact", "Contact us"],
  ["/earn", "Invite & earn"],
  ["/sell", "Sell on TryOnU"],
  ["/extension", "Browser extension"],
  ["/privacy", "Privacy"],
  ["/terms", "Terms of use"],
  ["/photo-policy", "Photo & data policy"],
  ["/affiliate-disclosure", "Affiliate disclosure"],
];

// where "back" goes when there is nothing to go back to (opened from a link or the home screen)
const PARENTS: [string, string][] = [
  ["/community/", "/community"],
  ["/u/", "/community"],
  ["/saved/", "/saved"],
  ["/stores/", "/try"],
  ["/look/", "/"],
];

function titleFor(path: string): string | null {
  const hit = TITLES.find(([prefix]) => (prefix.endsWith("/") ? path.startsWith(prefix) : path === prefix || path.startsWith(`${prefix}/`)));
  return hit ? hit[1] : null;
}

/** Phones' top bar, left side: the logo on the main tabs, "← screen name" everywhere else. */
export function PhoneTitle() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const [docTitle, setDocTitle] = useState<string | null>(null);
  const root = ROOTS.includes(pathname);

  // screens not in the list use the page's own title ("Pink lehenga · TryOnU" → "Pink lehenga")
  useEffect(() => {
    if (root || titleFor(pathname)) return;
    const read = () => setDocTitle(document.title.split(/ [·|] /)[0] || null);
    read();
    const t = setTimeout(read, 600);
    return () => clearTimeout(t);
  }, [pathname, root]);

  if (root) {
    return (
      <span className="lg:hidden">
        <Logo size={28} />
      </span>
    );
  }
  const title = titleFor(pathname) ?? docTitle ?? "TryOnU";
  const back = () => {
    const sameSite = typeof document !== "undefined" && document.referrer.startsWith(window.location.origin);
    if (window.history.length > 1 && sameSite) router.back();
    else router.push(PARENTS.find(([p]) => pathname.startsWith(p))?.[1] ?? "/me");
  };
  return (
    <div className="flex min-w-0 flex-1 items-center gap-1 lg:hidden">
      <button
        type="button"
        onClick={back}
        aria-label="Back"
        className="tu-tap -ml-2 grid h-11 w-11 shrink-0 place-items-center rounded-full text-ink active:bg-paper-2"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M15 5l-7 7 7 7" />
        </svg>
      </button>
      <span className="truncate text-[18px] font-semibold text-ink">{title}</span>
    </div>
  );
}
