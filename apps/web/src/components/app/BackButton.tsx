"use client";

import { useRouter } from "next/navigation";

/** A screen's "←": back where you came from, or to `fallback` when opened directly
 * (the installed app has no browser back button). Phones only. */
export function BackButton({ fallback = "/", className = "" }: { fallback?: string; className?: string }) {
  const router = useRouter();
  return (
    <button
      type="button"
      aria-label="Back"
      onClick={() => {
        const sameSite = document.referrer.startsWith(window.location.origin);
        if (window.history.length > 1 && sameSite) router.back();
        else router.push(fallback);
      }}
      className={`tu-tap grid h-11 w-11 place-items-center rounded-full text-ink active:bg-paper-2 lg:hidden ${className}`}
    >
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M15 5l-7 7 7 7" />
      </svg>
    </button>
  );
}
