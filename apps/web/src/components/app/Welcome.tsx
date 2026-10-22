"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { preferences } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const SEEN_KEY = "tu_welcome_seen";
const NEW_ACCOUNT_DAYS = 3;

const STEPS: { title: string; text: string }[] = [
  { title: "Add your photo", text: "One clear photo of you, standing. Only you can see it." },
  { title: "Pick clothes", text: "Search, ask the AI Stylist, or upload a photo of a look you like." },
  { title: "See it on you", text: "Like it? Tap Shop now to buy it from the shop." },
];

/** Three short steps the first time a new member opens TryOnU, with Skip. Shown once. */
export function Welcome() {
  const { user } = useSession();
  // after the country and "where do you like to shop" questions, never on top of them
  const prefs = useQuery({ queryKey: ["preferences"], queryFn: preferences.get, enabled: !!user });
  const answered = !!prefs.data?.country && !!prefs.data?.shop_from;
  const pathname = usePathname() || "/";
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!user || !answered || /^\/(admin|business|developers|sign-in|sign-up|try|app)/.test(pathname)) return;
    const isNew = Date.now() - new Date(user.created_at).getTime() < NEW_ACCOUNT_DAYS * 86_400_000;
    let seen = true;
    try {
      seen = localStorage.getItem(SEEN_KEY) === "1";
    } catch {
      // storage blocked: never show it rather than show it on every page
    }
    if (isNew && !seen) setOpen(true);
  }, [user, pathname, answered]);

  if (!open) return null;
  const close = () => {
    try {
      localStorage.setItem(SEEN_KEY, "1");
    } catch {
      // nothing to remember it in
    }
    setOpen(false);
  };
  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-3 sm:items-center" role="dialog" aria-modal="true" aria-label="Welcome to TryOnU">
      <div className="max-h-[90vh] w-full max-w-[420px] overflow-y-auto rounded-[26px] bg-surface p-5 pb-[calc(20px+env(safe-area-inset-bottom))] shadow-lift sm:pb-5">
        <p className="text-center text-[22px] font-semibold text-ink">Welcome{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}!</p>
        <p className="mt-1 text-center text-[15px] text-muted">Try clothes on your own photo in 3 easy steps.</p>
        <ol className="mt-5 space-y-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex items-start gap-3 rounded-2xl bg-paper-2 p-3.5">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-sage text-[15px] font-semibold text-white" aria-hidden="true">
                {i + 1}
              </span>
              <span className="min-w-0">
                <span className="block text-[16.5px] font-semibold text-ink">
                  {s.title}
                </span>
                <span className="block text-[14.5px] leading-snug text-muted">{s.text}</span>
              </span>
            </li>
          ))}
        </ol>
        <Link href="/try" onClick={close} className="tu-press mt-5 flex min-h-[52px] items-center justify-center rounded-full bg-sage text-[17px] font-semibold text-white">
          Start now
        </Link>
        <button type="button" onClick={close} className="tu-tap mt-2 min-h-[46px] w-full rounded-full text-[15.5px] font-semibold text-muted">
          Skip
        </button>
      </div>
    </div>
  );
}
