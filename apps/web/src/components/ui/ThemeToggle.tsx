"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";
const KEY = "tryonu-theme";

function systemTheme(): Theme {
  return typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function ThemeToggle({ className = "" }: { className?: string }) {
  const [mounted, setMounted] = useState(false);
  const [resolved, setResolved] = useState<Theme>("light");

  useEffect(() => {
    setMounted(true);
    let stored: Theme | null = null;
    try {
      const v = localStorage.getItem(KEY);
      if (v === "light" || v === "dark") stored = v;
    } catch {}
    setResolved(stored ?? systemTheme());

    // keep the icon honest if the OS theme changes while in "system" mode
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      let hasStored = false;
      try {
        hasStored = localStorage.getItem(KEY) !== null;
      } catch {}
      if (!hasStored) setResolved(mq.matches ? "dark" : "light");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = () => {
    const next: Theme = resolved === "dark" ? "light" : "dark";
    setResolved(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {}
  };

  const isDark = resolved === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={
        mounted
          ? `Switch to ${isDark ? "light" : "dark"} theme`
          : "Toggle theme"
      }
      aria-pressed={mounted ? isDark : undefined}
      className={`group/tt grid h-9 w-9 transform-gpu place-items-center rounded-full border border-line text-ink-soft transition-[background-color,color,transform,border-color] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-0.5 hover:border-line-strong hover:bg-ink/[0.06] hover:text-ink active:scale-95 ${className}`}
    >
      {/* render a stable icon until mounted to avoid hydration mismatch */}
      <span
        suppressHydrationWarning
        className="transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover/tt:rotate-[35deg] group-active/tt:scale-90"
      >
        {mounted && isDark ? <MoonIcon /> : <SunIcon />}
      </span>
    </button>
  );
}

function SunIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}
