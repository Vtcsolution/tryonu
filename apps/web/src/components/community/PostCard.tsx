"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Comments } from "@/components/community/CommentThread";
import { ChallengeChip, PollBox } from "@/components/community/extras";
import {
  Avatar,
  BookmarkIcon,
  CommentIcon,
  HangerIcon,
  LinkCards,
  ProductChips,
  RichText,
  SendIcon,
  ThumbIcon,
  timeAgo,
} from "@/components/community/parts";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { community, type CommunityPost } from "@/lib/api/endpoints";

// kept here too, for the pages that import them from the post card
export { Avatar, CommentIcon, HangerIcon, HeartIcon, ThumbIcon, timeAgo } from "@/components/community/parts";
export { Comments } from "@/components/community/CommentThread";

/** One post in the community: who posted it, the picture or video, the
 * products, and a LinkedIn-style bar (you · like · comment · send · who liked it). */
export function PostCard({
  post,
  onChange,
  onRemoved,
  openComments = false,
}: {
  post: CommunityPost;
  onChange?: (p: CommunityPost) => void;
  onRemoved?: () => void;
  openComments?: boolean;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const [p, setP] = useState(post);
  const [showComments, setShowComments] = useState(openComments);
  const [menu, setMenu] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [showLikers, setShowLikers] = useState(false);
  const me = useQuery({ queryKey: ["community", "me"], queryFn: community.me });

  // like or unlike is decided at the click and passed along: the request
  // must not re-read the already-changed state (a first like was sent as an unlike)
  const like = useMutation({
    mutationFn: (want: boolean) => (want ? community.like(p.id) : community.unlike(p.id)),
    onMutate: (want: boolean) =>
      setP((prev) => {
        const mine = me.data ? { handle: me.data.handle, name: me.data.name, avatar_url: me.data.avatar_url } : null;
        const others = (prev.likers ?? []).filter((x) => x.handle !== mine?.handle);
        const next = {
          ...prev,
          liked_by_me: want,
          like_count: Math.max(0, prev.like_count + (want ? 1 : -1)),
          likers: want && mine ? [mine, ...others].slice(0, 3) : others,
        };
        onChange?.(next);
        return next;
      }),
    onSuccess: (res) =>
      setP((prev) => {
        const next = { ...prev, liked_by_me: res.liked, like_count: res.like_count };
        onChange?.(next);
        return next;
      }),
    onError: (_err, want) =>
      setP((prev) => ({ ...prev, liked_by_me: !want, like_count: Math.max(0, prev.like_count + (want ? -1 : 1)) })),
  });
  // like the like: the wish is decided at the tap
  const save = useMutation({
    mutationFn: (want: boolean) => (want ? community.save(p.id) : community.unsave(p.id)),
    onMutate: (want: boolean) => setP((prev) => ({ ...prev, saved_by_me: want })),
    onError: (_e, want) => setP((prev) => ({ ...prev, saved_by_me: !want })),
    onSettled: () => qc.invalidateQueries({ queryKey: ["community", "saved"] }),
  });
  const follow = useMutation({
    mutationFn: () => community.follow(p.author.handle),
    onSuccess: () => {
      setP((prev) => ({ ...prev, following_author: true }));
      qc.invalidateQueries({ queryKey: ["community", "profile", p.author.handle] });
    },
  });
  const tryIt = useMutation({
    mutationFn: () => community.tryLook(p.id),
    onSuccess: (res) => router.push(res.outfit_id ? `/try?outfit=${res.outfit_id}` : `/try?product=${res.product_id}`),
  });
  const remove = useMutation({ mutationFn: () => community.remove(p.id), onSuccess: () => onRemoved?.() });
  const report = useMutation({
    mutationFn: (reason: string) => community.report({ post_id: p.id, reason }),
    onSuccess: () => setNotice("Thanks for telling us. Our team will look at it."),
  });

  const image = resolveMediaUrl(p.image_url);
  // a try-on look has products to put on yourself; a member's own photo or video doesn't
  const canTry = (p.media_kind ?? "tryon") === "tryon";
  const likers = p.likers ?? [];
  return (
    <article className="overflow-hidden rounded-[22px] border border-line bg-surface">
      <header className="flex items-center gap-3 px-4 py-3">
        <Link href={`/u/${p.author.handle}`} className="flex min-w-0 flex-1 items-center gap-3">
          <Avatar name={p.author.name} handle={p.author.handle} url={p.author.avatar_url} />
          <span className="min-w-0">
            <span className="block truncate text-[15.5px] font-semibold text-ink">{p.author.name || p.author.handle}</span>
            <span className="block truncate text-[13px] text-muted">
              @{p.author.handle} · {timeAgo(p.created_at)}
            </span>
          </span>
        </Link>
        {!p.is_mine && !p.following_author && (
          <button
            type="button"
            onClick={() => follow.mutate()}
            disabled={follow.isPending}
            className="tu-press min-h-[36px] rounded-full bg-ink px-4 text-[13.5px] font-semibold text-surface"
          >
            Follow
          </button>
        )}
        <div className="relative">
          <button
            type="button"
            aria-label="More"
            onClick={() => setMenu((m) => !m)}
            className="grid h-9 w-9 place-items-center rounded-full text-[20px] text-muted hover:bg-paper-2 hover:text-ink"
          >
            ⋯
          </button>
          {menu && (
            <div className="absolute right-0 top-10 z-20 w-56 rounded-xl border border-line bg-surface p-1 shadow-lift">
              {p.is_mine ? (
                <button
                  type="button"
                  onClick={() => {
                    setMenu(false);
                    if (window.confirm("Delete this post? It disappears from the community.")) remove.mutate();
                  }}
                  className="w-full rounded-lg px-3 py-2 text-left text-[14.5px] text-[#a4553f] hover:bg-paper-2"
                >
                  Delete post
                </button>
              ) : (
                ["Not appropriate", "Not a real look / spam", "Someone else's photo"].map((reason) => (
                  <button
                    key={reason}
                    type="button"
                    onClick={() => {
                      setMenu(false);
                      report.mutate(reason);
                    }}
                    className="w-full rounded-lg px-3 py-2 text-left text-[14.5px] text-ink hover:bg-paper-2"
                  >
                    Report: {reason}
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </header>

      {p.media_kind === "video" && p.video_url ? (
        <div className="bg-black">
          <video
            src={resolveMediaUrl(p.video_url)}
            poster={p.poster_url ? resolveMediaUrl(p.poster_url) : undefined}
            controls
            playsInline
            preload="metadata"
            className="mx-auto max-h-[720px] w-full object-contain"
          />
        </div>
      ) : (
        image && (
          <Link href={`/community/post/${p.id}`} className="block bg-paper-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={image} alt={p.caption || `A post by @${p.author.handle}`} loading="lazy" className="mx-auto max-h-[720px] w-full object-contain" />
          </Link>
        )
      )}

      <div className="px-4 pb-1 pt-3">
        {p.caption && (
          <p className="whitespace-pre-wrap break-words text-[15.5px] leading-relaxed text-ink">
            <Link href={`/u/${p.author.handle}`} className="font-semibold">@{p.author.handle}</Link> <RichText text={p.caption} />
          </p>
        )}
        <LinkCards previews={p.previews} />
        <ChallengeChip post={p} />

        <ProductChips products={p.products} className={p.caption ? "mt-3" : ""} />
        {(p.media_kind === "image" || p.media_kind === "video") && (
          <Link
            href={`/find-look?post=${p.id}`}
            className="mt-3 inline-flex min-h-[40px] items-center gap-2 rounded-full border border-line-strong px-4 text-[14px] font-semibold text-ink hover:border-sage"
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
              <circle cx="12" cy="12" r="3.5" />
            </svg>
            Find these products
          </Link>
        )}

        {p.poll && (
          <PollBox
            post={p}
            onChange={(patch) =>
              setP((prev) => {
                const next = { ...prev, ...patch };
                onChange?.(next);
                return next;
              })
            }
          />
        )}

        {canTry && (
          <button
            type="button"
            onClick={() => tryIt.mutate()}
            disabled={tryIt.isPending}
            className="tu-press tu-attention mt-3 flex min-h-[46px] w-full items-center justify-center gap-2 rounded-full bg-sage-tint/45 text-[15px] font-semibold text-sage-deep hover:bg-sage-tint/70 disabled:opacity-60"
          >
            <HangerIcon />
            {tryIt.isPending ? "Opening…" : "Try this look on yourself"}
          </button>
        )}
        {tryIt.isError && <p className="mt-2 text-[14px] text-[#a4553f]">{tryIt.error instanceof ApiError ? tryIt.error.detail : "Couldn't open this look."}</p>}

        {/* the bar, like LinkedIn: you · like · comment · send ........ who liked it */}
        <div className="mt-3 flex items-center gap-0.5 border-t border-line pt-2 sm:gap-1">
          {me.data && (
            <Link href={`/u/${me.data.handle}`} title="Your profile" className="mr-1 shrink-0 rounded-full">
              <Avatar name={me.data.name} handle={me.data.handle} url={me.data.avatar_url} size={28} />
            </Link>
          )}
          <BarButton
            label={p.liked_by_me ? "Unlike" : "Like"}
            count={p.like_count}
            pressed={p.liked_by_me}
            onClick={() => !like.isPending && like.mutate(!p.liked_by_me)}
            className={p.liked_by_me ? "text-sage-deep" : undefined}
          >
            <ThumbIcon filled={p.liked_by_me} />
          </BarButton>
          <BarButton label="Comment" count={p.comment_count} pressed={showComments} onClick={() => setShowComments((v) => !v)}>
            <CommentIcon size={20} />
          </BarButton>
          <ShareButton post={p} />
          <BarButton
            label={p.saved_by_me ? "Saved: tap to remove" : "Save for later"}
            pressed={!!p.saved_by_me}
            onClick={() => !save.isPending && save.mutate(!p.saved_by_me)}
            className={p.saved_by_me ? "text-sage-deep" : undefined}
          >
            <BookmarkIcon filled={!!p.saved_by_me} />
          </BarButton>
          <span className="flex-1" />
          {likers.length > 0 && (
            <button
              type="button"
              onClick={() => setShowLikers(true)}
              title="See who liked this"
              aria-label={`See who liked this (${p.like_count})`}
              className="flex shrink-0 items-center rounded-full p-1 hover:bg-paper-2"
            >
              {likers.slice(0, 3).map((x, i) => (
                <Avatar
                  key={x.handle}
                  name={x.name}
                  handle={x.handle}
                  url={x.avatar_url}
                  size={24}
                  className={`ring-2 ring-surface ${i > 0 ? "-ml-2" : ""} ${i === 2 ? "hidden sm:grid" : ""}`}
                />
              ))}
            </button>
          )}
        </div>
        {notice && <p className="mt-2 rounded-xl bg-sage-tint/40 px-3 py-2 text-[14px] text-ink">{notice}</p>}

        {showComments && <Comments post={p} onCount={(n) => setP((prev) => ({ ...prev, comment_count: n }))} />}
        <div className="h-3" />
      </div>
      {showLikers && <LikersDialog postId={p.id} onClose={() => setShowLikers(false)} />}
    </article>
  );
}

/** A button of the bar: an outline icon and its count. */
function BarButton({
  children,
  label,
  count,
  onClick,
  pressed,
  className,
}: {
  children: React.ReactNode;
  label: string;
  count?: number;
  onClick: () => void;
  pressed?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      aria-label={count ? `${label} (${count})` : label}
      title={label}
      className={`flex h-10 min-w-[40px] items-center justify-center gap-1.5 rounded-lg px-1.5 text-[14.5px] font-semibold transition-colors hover:bg-paper-2 sm:min-w-[44px] sm:px-2.5 ${
        className ?? "text-ink-soft hover:text-ink"
      }`}
    >
      {children}
      {count ? <span className="tabular-nums">{count}</span> : null}
    </button>
  );
}

/** Send: copy the link or share it to WhatsApp, Facebook, LinkedIn or X. */
function ShareButton({ post }: { post: CommunityPost }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const url = typeof window !== "undefined" ? `${window.location.origin}/community/post/${post.id}` : "";
  const text = post.caption ? `${post.caption} — on TryOnU` : `A look by @${post.author.handle} on TryOnU`;
  const enc = encodeURIComponent;
  const targets = [
    { name: "WhatsApp", href: `https://wa.me/?text=${enc(`${text} ${url}`)}` },
    { name: "Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${enc(url)}` },
    { name: "LinkedIn", href: `https://www.linkedin.com/sharing/share-offsite/?url=${enc(url)}` },
    { name: "X", href: `https://twitter.com/intent/tweet?text=${enc(text)}&url=${enc(url)}` },
  ];
  return (
    <div ref={ref} className="relative">
      <BarButton label="Send" pressed={open} onClick={() => setOpen((v) => !v)}>
        <SendIcon />
      </BarButton>
      {open && (
        <div role="menu" className="absolute bottom-full left-0 z-20 mb-2 w-60 rounded-xl border border-line bg-surface p-1 shadow-lift">
          <button
            type="button"
            role="menuitem"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(url);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              } catch {
                window.prompt("Copy this link", url);
              }
            }}
            className="w-full rounded-lg px-3 py-2.5 text-left text-[14.5px] font-semibold text-ink hover:bg-paper-2"
          >
            {copied ? "Link copied ✓" : "Copy link"}
          </button>
          {targets.map((t) => (
            <a
              key={t.name}
              role="menuitem"
              href={t.href}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-2.5 text-[14.5px] text-ink hover:bg-paper-2"
            >
              Share on {t.name}
            </a>
          ))}
          {typeof navigator !== "undefined" && "share" in navigator && (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                navigator.share({ title: "TryOnU", text, url }).catch(() => undefined);
              }}
              className="w-full rounded-lg px-3 py-2.5 text-left text-[14.5px] text-ink hover:bg-paper-2"
            >
              More…
            </button>
          )}
          <p className="px-3 pb-1.5 pt-1 text-[12px] text-faint">Friends sign in to TryOnU to see community posts.</p>
        </div>
      )}
    </div>
  );
}

/** Everyone who liked a post. */
function LikersDialog({ postId, onClose }: { postId: string; onClose: () => void }) {
  const list = useQuery({ queryKey: ["community", "likers", postId], queryFn: () => community.likers(postId) });
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label="Likes" className="flex max-h-[70vh] w-full max-w-[420px] flex-col rounded-[20px] bg-surface shadow-lift">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <p className="text-[16px] font-semibold text-ink">Liked by</p>
          <button type="button" onClick={onClose} aria-label="Close" className="grid h-9 w-9 place-items-center rounded-lg text-[22px] text-muted hover:bg-paper-2">
            ×
          </button>
        </div>
        <div className="overflow-y-auto p-2">
          {list.isLoading && <p className="p-3 text-[14px] text-muted">Loading…</p>}
          {list.data?.map((x) => (
            <Link key={x.handle} href={`/u/${x.handle}`} className="flex items-center gap-3 rounded-xl px-3 py-2 hover:bg-paper-2">
              <span className="relative">
                <Avatar name={x.name} handle={x.handle} url={x.avatar_url} size={40} />
                <span className="absolute -bottom-0.5 -right-0.5 grid h-[18px] w-[18px] place-items-center rounded-full bg-sage-deep text-white ring-2 ring-surface">
                  <ThumbIcon filled size={10} />
                </span>
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[15px] font-semibold text-ink">{x.name || `@${x.handle}`}</span>
                <span className="block truncate text-[13px] text-muted">@{x.handle}</span>
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
