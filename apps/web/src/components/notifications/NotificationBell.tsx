"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { BellIcon, NotificationRow } from "@/components/notifications/NotificationRow";
import { notifications, type AppNotification } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

export const UNREAD_KEY = ["notifications", "unread"];

/** The bell in the header: a red count of what's new, and the latest few on a click. */
export function NotificationBell() {
  const { user } = useSession();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const unread = useQuery({
    queryKey: UNREAD_KEY,
    queryFn: notifications.unread,
    enabled: !!user,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
  const latest = useQuery({ queryKey: ["notifications", "latest"], queryFn: () => notifications.list(0, 8), enabled: !!user && open, staleTime: 0 });
  const readAll = useMutation({
    mutationFn: notifications.readAll,
    onSuccess: () => {
      qc.setQueryData(UNREAD_KEY, { unread: 0 });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // a phone notification arrived while the site is open: refresh the count
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "tryonu-notification") qc.invalidateQueries({ queryKey: ["notifications"] });
    };
    navigator.serviceWorker.addEventListener("message", onMessage);
    return () => navigator.serviceWorker.removeEventListener("message", onMessage);
  }, [qc]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  if (!user) return null;
  const count = unread.data?.unread ?? 0;
  const opened = (n: AppNotification) => {
    setOpen(false);
    if (!n.read) notifications.read(n.id).then((r) => qc.setQueryData(UNREAD_KEY, r)).catch(() => undefined);
  };
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={count ? `Notifications, ${count} new` : "Notifications"}
        title="Notifications"
        className="relative grid h-10 w-10 place-items-center rounded-full text-ink-soft transition-colors hover:bg-paper-2 hover:text-ink"
      >
        <BellIcon />
        {count > 0 && (
          <span className="absolute right-0.5 top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-[#c0503a] px-1 text-[11px] font-bold leading-none text-white ring-2 ring-paper">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-x-3 top-[76px] z-50 rounded-2xl border border-line bg-surface shadow-lift sm:absolute sm:inset-x-auto sm:right-0 sm:top-12 sm:w-[400px]">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="text-[16px] font-semibold text-ink">Notifications</p>
            {count > 0 && (
              <button type="button" onClick={() => readAll.mutate()} className="text-[13.5px] font-semibold text-sage-deep hover:underline">
                Mark all as read
              </button>
            )}
          </div>
          <div className="max-h-[min(460px,70vh)] overflow-y-auto p-1.5">
            {latest.isLoading && <p className="px-3 py-6 text-center text-[14px] text-muted">Loading…</p>}
            {latest.data && latest.data.items.length === 0 && (
              <p className="px-3 py-8 text-center text-[14.5px] text-muted">
                Nothing yet. When people like or comment on your looks, you&apos;ll see it here.
              </p>
            )}
            {latest.data?.items.map((n) => <NotificationRow key={n.id} n={n} onOpen={opened} compact />)}
          </div>
          <Link
            href="/notifications"
            onClick={() => setOpen(false)}
            className="block border-t border-line px-4 py-3 text-center text-[14.5px] font-semibold text-ink hover:bg-paper-2"
          >
            See all notifications
          </Link>
        </div>
      )}
    </div>
  );
}
