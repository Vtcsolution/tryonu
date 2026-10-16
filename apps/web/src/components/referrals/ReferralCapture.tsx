"use client";

import { useEffect } from "react";
import { referrals as referralsApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const KEY = "tou_ref";

/** Remember the link a visitor came from (a shared look, or ?ref=<code>). */
export function rememberReferral(ref: string) {
  try {
    if (!localStorage.getItem(KEY)) localStorage.setItem(KEY, ref);
  } catch {
    // private window: nothing to remember
  }
}

/** Share and earn: notes ?ref= on any page, and once the visitor has an
 * account, tells TryOnU which link brought them (the server only accepts
 * this for a brand-new account, once). */
export function ReferralCapture() {
  const { user } = useSession();

  useEffect(() => {
    const ref = new URLSearchParams(window.location.search).get("ref");
    if (ref && /^[a-z0-9]{4,16}$/i.test(ref)) rememberReferral(ref);
  }, []);

  useEffect(() => {
    if (!user) return;
    let ref: string | null = null;
    try {
      ref = localStorage.getItem(KEY);
    } catch {
      return;
    }
    if (!ref) return;
    referralsApi
      .claim(ref)
      .then(() => {
        try {
          localStorage.removeItem(KEY);
        } catch {
          // ignore
        }
      })
      .catch(() => undefined);
  }, [user]);

  return null;
}
