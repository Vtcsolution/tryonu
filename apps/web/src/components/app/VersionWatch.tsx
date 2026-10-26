"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const MINE = process.env.NEXT_PUBLIC_BUILD_ID ?? "";
const CHECK_EVERY_MS = 5 * 60_000;

/** After TryOnU is updated, a tab opened before the update still runs the old
 * page code; moving to another page then mixed old code with new pages
 * (stretched pictures, old wording). This notices the update and loads the
 * next page fresh, so nobody sees that mix. Nothing reloads while they stay
 * on a page, so nothing they're typing is lost. */
export function VersionWatch() {
  const pathname = usePathname();
  const stale = useRef(false);
  const first = useRef(true);

  useEffect(() => {
    if (!MINE) return;
    const check = async () => {
      try {
        const res = await fetch("/version", { cache: "no-store" });
        if (!res.ok) return;
        const { id } = (await res.json()) as { id?: string };
        if (id && id !== MINE) stale.current = true;
      } catch {
        // offline or between deploys: try again later
      }
    };
    check();
    const timer = setInterval(check, CHECK_EVERY_MS);
    const onVisible = () => document.visibilityState === "visible" && check();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  // the site was updated: this page change loads fresh
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (stale.current) window.location.reload();
  }, [pathname]);

  return null;
}
