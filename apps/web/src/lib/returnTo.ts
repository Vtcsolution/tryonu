"use client";

import { useEffect, useState } from "react";

/** A look (or post) someone shared, opened before the visitor had an account.
 * Remembered for a week so it is waiting for them after sign-up, whichever way
 * they get there (email link, Google, the top "Sign up" button). */
const KEY = "tu_return_to";
const KEEP_MS = 7 * 86_400_000;

export function rememberReturnTo(path: string) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ path, at: Date.now() }));
  } catch {
    // private window: nothing to remember
  }
}

export function pendingReturnTo(): string | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const { path, at } = JSON.parse(raw) as { path?: string; at?: number };
    if (!path || !safePath(path) || !at || Date.now() - at > KEEP_MS) {
      localStorage.removeItem(KEY);
      return null;
    }
    return path;
  } catch {
    return null;
  }
}

/** Opened: no need to offer it again. */
export function clearReturnTo(path?: string) {
  try {
    if (!path || pendingReturnTo() === path) localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}

/** Only our own pages, never another site. */
export function safePath(path: string | null | undefined): path is string {
  return !!path && path.startsWith("/") && !path.startsWith("//") && !path.includes("\\");
}

/** The remembered page, read after the page has loaded in the browser. */
export function usePendingReturnTo(): string | null {
  const [path, setPath] = useState<string | null>(null);
  useEffect(() => setPath(pendingReturnTo()), []);
  return path;
}
