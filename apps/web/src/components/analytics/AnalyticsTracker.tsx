"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { API_BASE_URL } from "@/lib/api/client";

const VISITOR_KEY = "tryonu-vid";
const SESSION_KEY = "tryonu-sid";
const SESSION_IDLE_MS = 30 * 60 * 1000;

// document.referrer only describes the full page load, not later client-side
// navigations, so it's reported once per load.
let referrerReported = false;

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`;
}

function visitorAndSession(): { visitor: string; session: string } | null {
  try {
    let visitor = localStorage.getItem(VISITOR_KEY);
    if (!visitor) {
      visitor = newId();
      localStorage.setItem(VISITOR_KEY, visitor);
    }
    const now = Date.now();
    const [storedId, lastSeen] = (localStorage.getItem(SESSION_KEY) ?? "").split("|");
    const session = storedId && now - Number(lastSeen) < SESSION_IDLE_MS ? storedId : newId();
    localStorage.setItem(SESSION_KEY, `${session}|${now}`);
    return { visitor, session };
  } catch {
    return null; // storage blocked (private mode, etc.) — skip rather than count every view as new
  }
}

function trackingAllowed(): boolean {
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return !(nav.globalPrivacyControl || nav.doNotTrack === "1");
}

/** Records one page view per route (never on /admin) plus the time the
 * page was actually visible, for the admin Analytics section. Only random
 * ids are sent — no personal data. */
export function AnalyticsTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (!pathname || pathname.startsWith("/admin") || !trackingAllowed()) return;
    const ids = visitorAndSession();
    if (!ids) return;

    const referrer = referrerReported ? undefined : document.referrer || undefined;
    referrerReported = true;

    const created: Promise<{ id: string } | null> = fetch(`${API_BASE_URL}/api/v1/analytics/pageview`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: pathname, referrer, visitor_id: ids.visitor, session_id: ids.session }),
    })
      .then((r) => (r.status === 201 ? (r.json() as Promise<{ id: string }>) : null))
      .catch(() => null);

    let visibleMs = 0;
    let visibleSince: number | null = document.visibilityState === "visible" ? performance.now() : null;
    const pause = () => {
      if (visibleSince !== null) {
        visibleMs += performance.now() - visibleSince;
        visibleSince = null;
      }
    };

    const report = () => {
      const durationMs = Math.round(visibleMs + (visibleSince !== null ? performance.now() - visibleSince : 0));
      void created.then((view) => {
        if (!view) return;
        const url = `${API_BASE_URL}/api/v1/analytics/pageview/${view.id}/duration`;
        const body = JSON.stringify({ visitor_id: ids.visitor, duration_ms: durationMs });
        // text/plain keeps this a CORS "simple" request so it survives page unload
        const queued = navigator.sendBeacon?.(url, new Blob([body], { type: "text/plain" }));
        if (!queued) {
          fetch(url, { method: "POST", body, headers: { "Content-Type": "text/plain" }, keepalive: true }).catch(() => {});
        }
      });
    };

    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        pause();
        report();
      } else if (visibleSince === null) {
        visibleSince = performance.now();
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", report);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", report);
      report(); // navigated to another route
    };
  }, [pathname]);

  return null;
}
