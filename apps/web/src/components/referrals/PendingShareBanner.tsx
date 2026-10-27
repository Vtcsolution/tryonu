"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "@/lib/auth/useSession";
import { clearReturnTo, pendingReturnTo } from "@/lib/returnTo";

/** A signed-in member who opened a shared look or post before they had an
 * account, and hasn't opened it since: it is waiting at the top of the page. */
export function PendingShareBanner() {
  const { user } = useSession();
  const pathname = usePathname() || "/";
  const [path, setPath] = useState<string | null>(null);

  useEffect(() => {
    setPath(user ? pendingReturnTo() : null);
  }, [user, pathname]);

  if (!user || !path || pathname === path || /^\/(sign-in|sign-up|verify-email|preferences|looks?\/)/.test(pathname))
    return null;
  const isLook = path.startsWith("/look/") || path.startsWith("/looks/");
  return (
    <div className="tu-container pt-3">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-3 rounded-[20px] border border-sage/40 bg-sage-tint/30 px-4 py-3">
        <p className="min-w-0 flex-1 text-[15.5px] font-semibold text-ink">
          {isLook ? "The look shared with you is ready to try on." : "The post shared with you is waiting."}
        </p>
        <Link
          href={path}
          onClick={() => setPath(null)}
          className="tu-press inline-flex min-h-[44px] items-center rounded-full bg-sage px-5 text-[15px] font-semibold text-white"
        >
          {isLook ? "Try it on" : "Open it"}
        </Link>
        <button
          type="button"
          onClick={() => {
            clearReturnTo();
            setPath(null);
          }}
          className="min-h-[44px] px-2 text-[14px] text-muted hover:text-ink"
        >
          Not now
        </button>
      </div>
    </div>
  );
}
