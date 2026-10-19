"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { UNREAD_KEY } from "@/components/notifications/NotificationBell";
import { NotificationRow } from "@/components/notifications/NotificationRow";
import { InstallAppCard } from "@/components/pwa/InstallApp";
import { ApiError } from "@/lib/api/client";
import { notifications, type AppNotification, type NotificationSettings } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import { currentSubscription, pushSupported, subscribe, unsubscribe } from "@/lib/pwa";

/** /notifications: everything that happened, and how to be told about it. */
export function NotificationsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace("/sign-in?next=/notifications");
  }, [isLoading, user, router]);
  const list = useInfiniteQuery({
    queryKey: ["notifications", "page"],
    queryFn: ({ pageParam }) => notifications.list(pageParam, 20),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    enabled: !!user,
    staleTime: 0,
  });
  const readAll = useMutation({
    mutationFn: notifications.readAll,
    onSuccess: () => {
      qc.setQueryData(UNREAD_KEY, { unread: 0 });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  if (!user) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const unread = list.data?.pages[0]?.unread ?? 0;
  const opened = (n: AppNotification) => {
    if (!n.read) notifications.read(n.id).then((r) => qc.setQueryData(UNREAD_KEY, r)).catch(() => undefined);
  };
  return (
    <section className="tu-container py-8 md:py-12">
      <div className="mx-auto grid max-w-[1000px] gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-[clamp(28px,4vw,40px)] leading-tight text-ink">Notifications</h1>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => readAll.mutate()}
                className="tu-press min-h-[44px] rounded-full border border-line-strong px-4 text-[14.5px] font-semibold text-ink"
              >
                Mark all as read
              </button>
            )}
          </div>
          <div className="mt-5 rounded-[22px] border border-line bg-surface p-2">
            {list.isLoading && Array.from({ length: 4 }).map((_, i) => <div key={i} className="m-2 h-14 animate-pulse rounded-xl bg-paper-2" />)}
            {!list.isLoading && items.length === 0 && (
              <div className="px-4 py-12 text-center">
                <p className="text-[17px] font-semibold text-ink">Nothing yet</p>
                <p className="mt-1 text-[15px] text-muted">
                  When people like or comment on your looks, follow you, or you earn credits, you&apos;ll see it here.
                </p>
              </div>
            )}
            {items.map((n) => <NotificationRow key={n.id} n={n} onOpen={opened} />)}
          </div>
          {list.hasNextPage && (
            <button
              type="button"
              onClick={() => list.fetchNextPage()}
              disabled={list.isFetchingNextPage}
              className="tu-press mt-4 min-h-[46px] w-full rounded-full border border-line-strong text-[15px] font-semibold text-ink"
            >
              {list.isFetchingNextPage ? "Loading…" : "Show older"}
            </button>
          )}
        </div>

        <aside className="space-y-4">
          <Settings />
          <InstallAppCard />
        </aside>
      </div>
    </section>
  );
}

function Settings() {
  const qc = useQueryClient();
  const key = ["notifications", "settings"];
  const settings = useQuery({ queryKey: key, queryFn: notifications.settings });
  const setEmail = useMutation({ mutationFn: notifications.setEmail, onSuccess: (s) => qc.setQueryData(key, s) });
  return (
    <div className="rounded-[20px] border border-line bg-surface p-5">
      <p className="text-[16px] font-semibold text-ink">How we tell you</p>
      <PhoneNotifications settings={settings.data} onChange={(s) => qc.setQueryData(key, s)} />
      <label className="mt-4 flex cursor-pointer items-start gap-3">
        <input
          type="checkbox"
          checked={settings.data?.email ?? true}
          disabled={!settings.data || setEmail.isPending}
          onChange={(e) => setEmail.mutate(e.target.checked)}
          className="mt-1 h-5 w-5 shrink-0 accent-[var(--color-sage)]"
        />
        <span>
          <span className="block text-[15px] font-semibold text-ink">Daily email</span>
          <span className="block text-[13.5px] text-muted">One short email a day at most, only when something new happened.</span>
        </span>
      </label>
    </div>
  );
}

function PhoneNotifications({ settings, onChange }: { settings?: NotificationSettings; onChange: (s: NotificationSettings) => void }) {
  const [on, setOn] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supported = pushSupported();
  useEffect(() => {
    currentSubscription().then((s) => setOn(!!s)).catch(() => setOn(false));
  }, []);

  const turnOn = async () => {
    if (!settings?.push_key) return;
    setBusy(true);
    setError(null);
    try {
      const sub = await subscribe(settings.push_key);
      onChange(await notifications.addPhone(sub));
      setOn(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : err instanceof Error && err.message === "blocked"
            ? "Notifications are blocked for TryOnU. Allow them in your browser's site settings, then try again."
            : "Couldn't turn on notifications on this device.",
      );
    } finally {
      setBusy(false);
    }
  };
  const turnOff = async () => {
    setBusy(true);
    try {
      const endpoint = await unsubscribe();
      if (endpoint) onChange(await notifications.removePhone(endpoint));
      setOn(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3">
      <p className="text-[15px] font-semibold text-ink">On this phone or computer</p>
      {!supported ? (
        <p className="mt-1 text-[13.5px] text-muted">
          This browser can&apos;t show notifications. On an iPhone, add TryOnU to your Home Screen first (see below), then open it from there.
        </p>
      ) : settings && !settings.push_key ? (
        <p className="mt-1 text-[13.5px] text-muted">Coming soon. Meanwhile the bell and the daily email keep you posted.</p>
      ) : (
        <>
          <p className="mt-1 text-[13.5px] text-muted">
            {on ? "On: you'll get a notification here when something happens." : "Get a notification here the moment someone likes, comments or follows you."}
          </p>
          <button
            type="button"
            onClick={on ? turnOff : turnOn}
            disabled={busy || on === null || !settings}
            className={`tu-press mt-3 min-h-[44px] w-full rounded-full text-[15px] font-semibold disabled:opacity-60 ${
              on ? "border border-line-strong text-ink" : "bg-sage text-white"
            }`}
          >
            {busy ? "One moment…" : on ? "Turn off on this device" : "Turn on notifications"}
          </button>
        </>
      )}
      {error && <p className="mt-2 text-[13.5px] text-[#a4553f]">{error}</p>}
    </div>
  );
}
