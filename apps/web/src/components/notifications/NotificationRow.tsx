"use client";

import Link from "next/link";
import { Avatar, CommentIcon, ThumbIcon, timeAgo } from "@/components/community/parts";
import { resolveMediaUrl } from "@/lib/api/client";
import type { AppNotification } from "@/lib/api/endpoints";

/** One notification: who, what, when, and the post it is about. */
export function NotificationRow({ n, onOpen, compact = false }: { n: AppNotification; onOpen: (n: AppNotification) => void; compact?: boolean }) {
  return (
    <Link
      href={n.url}
      onClick={() => onOpen(n)}
      className={`flex items-start gap-3 rounded-xl px-3 transition-colors hover:bg-paper-2 ${compact ? "py-2.5" : "py-3"} ${n.read ? "" : "bg-sage-tint/25"}`}
    >
      <span className="relative shrink-0">
        {n.actor ? (
          <Avatar name={n.actor.name} handle={n.actor.handle ?? "?"} url={n.actor.avatar_url} size={compact ? 40 : 46} />
        ) : (
          <span
            className="grid place-items-center rounded-full bg-sage-deep text-white"
            style={{ width: compact ? 40 : 46, height: compact ? 40 : 46 }}
            aria-hidden="true"
          >
            <CoinIcon />
          </span>
        )}
        <KindBadge kind={n.kind} />
      </span>
      <span className="min-w-0 flex-1">
        <span className={`block text-[14.5px] leading-snug ${n.read ? "text-ink-soft" : "font-medium text-ink"}`}>{n.text}</span>
        <span className={`mt-0.5 block text-[12.5px] ${n.read ? "text-faint" : "font-semibold text-sage-deep"}`}>{timeAgo(n.created_at)}</span>
      </span>
      {n.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={resolveMediaUrl(n.image_url)} alt="" loading="lazy" className="h-12 w-10 shrink-0 rounded-md bg-paper-2 object-cover object-top" />
      )}
      {!n.read && <span className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-sage" aria-label="New" />}
    </Link>
  );
}

function KindBadge({ kind }: { kind: string }) {
  const icon =
    kind === "post_like" || kind === "comment_like" ? (
      <ThumbIcon filled size={10} />
    ) : kind === "comment" || kind === "reply" ? (
      <CommentIcon size={10} />
    ) : kind === "follow" || kind === "referral_joined" ? (
      <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0z" />
      </svg>
    ) : null;
  if (!icon) return null;
  return (
    <span className="absolute -bottom-0.5 -right-0.5 grid h-[20px] w-[20px] place-items-center rounded-full bg-sage-deep text-white ring-2 ring-surface">
      {icon}
    </span>
  );
}

function CoinIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5v9M9.5 9.8c0-1.2 1.1-1.8 2.5-1.8s2.5.7 2.5 1.8c0 2.6-5 1.4-5 4.2 0 1.2 1.1 1.8 2.5 1.8s2.5-.6 2.5-1.8" />
    </svg>
  );
}

export function BellIcon({ size = 21 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 9.5a6 6 0 0 1 12 0c0 4.6 1.8 6.2 2.5 7H3.5c.7-.8 2.5-2.4 2.5-7z" />
      <path d="M10 19.5a2.2 2.2 0 0 0 4 0" />
    </svg>
  );
}
