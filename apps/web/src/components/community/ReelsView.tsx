"use client";

import Link from "next/link";
import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { SongLabel } from "@/components/community/Music";
import { Avatar, CommentIcon, Comments, HangerIcon, HeartIcon } from "@/components/community/PostCard";
import { formatPrice } from "@/components/try/shop";
import { resolveMediaUrl } from "@/lib/api/client";
import { community, type CommunityPost } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** /community/reels: one post per screen, swipe up for the next, like Reels and TikTok. */
export function ReelsView() {
  const router = useRouter();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace("/sign-in?next=/community/reels");
  }, [isLoading, user, router]);

  const feed = useInfiniteQuery({
    queryKey: ["community", "reels"],
    queryFn: ({ pageParam }) => community.feed("for_you", pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    enabled: !!user,
  });
  const posts = feed.data?.pages.flatMap((p) => p.posts) ?? [];
  const [active, setActive] = useState(0);
  const [muted, setMuted] = useState(true);
  const [commentsFor, setCommentsFor] = useState<CommunityPost | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  // One player for every post's song: phones only start sound after a tap, and
  // a player unlocked by that tap keeps playing the next posts' songs too.
  const song = useRef<HTMLAudioElement | null>(null);
  const songSrc = useRef<string | null>(null);
  const activeSong = posts[active]?.music;
  const songUrl = activeSong ? resolveMediaUrl(activeSong.url) : null;
  const playSong = useCallback((url: string | null, on: boolean) => {
    if (!song.current) {
      song.current = new Audio();
      song.current.loop = true;
    }
    const a = song.current;
    if (!url || !on) {
      a.pause();
      return;
    }
    if (songSrc.current !== url) {
      songSrc.current = url;
      a.src = url;
    }
    a.play().catch(() => undefined);
  }, []);
  useEffect(() => {
    playSong(songUrl, !muted && !commentsFor);
  }, [songUrl, muted, commentsFor, playSong]);
  useEffect(() => () => song.current?.pause(), []);
  const toggleMute = () => {
    const next = !muted;
    setMuted(next);
    playSong(songUrl, !next); // inside the tap, so phones allow the sound
  };

  // the slide that fills most of the screen is the one playing
  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.index));
      },
      { root, threshold: 0.6 },
    );
    root.querySelectorAll("[data-index]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [posts.length]);

  // keep loading as the viewer gets near the end
  useEffect(() => {
    if (active >= posts.length - 3 && feed.hasNextPage && !feed.isFetchingNextPage) feed.fetchNextPage();
  }, [active, posts.length, feed]);

  const go = useCallback((delta: number) => {
    const root = scroller.current;
    if (root) root.scrollBy({ top: delta * root.clientHeight, behavior: "smooth" });
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (commentsFor) return;
      if (e.key === "ArrowDown" || e.key === "PageDown") (e.preventDefault(), go(1));
      if (e.key === "ArrowUp" || e.key === "PageUp") (e.preventDefault(), go(-1));
      if (e.key === "m") setMuted((m) => !m);
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [go, commentsFor]);

  return (
    <div className="fixed inset-0 z-[70] bg-black text-white">
      <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between bg-gradient-to-b from-black/60 to-transparent px-4 pb-8 pt-4">
        <Link href="/community" className="flex items-center gap-2 text-[16px] font-semibold" aria-label="Back to the community">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 5l-7 7 7 7" />
          </svg>
          Reels
        </Link>
        <button
          type="button"
          onClick={toggleMute}
          aria-label={muted ? "Turn sound on" : "Turn sound off"}
          className="grid h-10 w-10 place-items-center rounded-full bg-white/15 backdrop-blur"
        >
          <SpeakerIcon muted={muted} />
        </button>
      </div>

      <div ref={scroller} className="tu-screen-h snap-y snap-mandatory overflow-y-scroll [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {feed.isLoading && (
          <div className="grid tu-screen-h place-items-center">
            <div className="h-9 w-9 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          </div>
        )}
        {!feed.isLoading && posts.length === 0 && (
          <div className="grid tu-screen-h place-items-center px-8 text-center">
            <div>
              <p className="text-[20px] font-semibold">No posts yet</p>
              <p className="mt-2 text-white/70">Be the first: post a look, a photo or a video.</p>
              <Link href="/community" className="mt-5 inline-flex min-h-[46px] items-center rounded-full bg-white px-5 font-semibold text-black">
                Back to the community
              </Link>
            </div>
          </div>
        )}
        {posts.map((p, i) => (
          <Slide
            key={p.id}
            index={i}
            post={p}
            playing={i === active && !commentsFor}
            near={Math.abs(i - active) <= 1}
            muted={muted}
            onToggleMute={toggleMute}
            onComments={() => setCommentsFor(p)}
          />
        ))}
      </div>

      {commentsFor &&
        createPortal(
          <div className="fixed inset-0 z-[80] flex items-end bg-black/40" onMouseDown={(e) => e.target === e.currentTarget && setCommentsFor(null)}>
            <div role="dialog" aria-modal="true" aria-label="Comments" className="max-h-[75vh] w-full overflow-y-auto rounded-t-[20px] bg-surface px-4 pb-6 pt-3 sm:mx-auto sm:max-w-[560px]">
              <div className="flex items-center justify-between">
                <p className="text-[16px] font-semibold text-ink">Comments</p>
                <button type="button" onClick={() => setCommentsFor(null)} aria-label="Close" className="grid h-9 w-9 place-items-center rounded-lg text-[22px] text-muted hover:bg-paper-2">
                  ×
                </button>
              </div>
              <Comments post={commentsFor} onCount={() => undefined} />
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}

function Slide({
  post,
  index,
  playing,
  near,
  muted,
  onToggleMute,
  onComments,
}: {
  post: CommunityPost;
  index: number;
  playing: boolean;
  near: boolean;
  muted: boolean;
  onToggleMute: () => void;
  onComments: () => void;
}) {
  const router = useRouter();
  const [p, setP] = useState(post);
  const [expanded, setExpanded] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const isVideo = p.media_kind === "video" && !!p.video_url;
  const canTry = (p.media_kind ?? "tryon") === "tryon";

  useEffect(() => {
    const v = video.current;
    if (!v) return;
    v.muted = muted || !!p.music;
    if (playing) v.play().catch(() => undefined);
    else v.pause();
  }, [playing, muted, p.music]);

  const like = useMutation({
    mutationFn: (want: boolean) => (want ? community.like(p.id) : community.unlike(p.id)),
    onMutate: (want: boolean) => setP((prev) => ({ ...prev, liked_by_me: want, like_count: Math.max(0, prev.like_count + (want ? 1 : -1)) })),
    onSuccess: (res) => setP((prev) => ({ ...prev, liked_by_me: res.liked, like_count: res.like_count })),
    onError: (_e, want) => setP((prev) => ({ ...prev, liked_by_me: !want, like_count: Math.max(0, prev.like_count + (want ? -1 : 1)) })),
  });
  const tryIt = useMutation({
    mutationFn: () => community.tryLook(p.id),
    onSuccess: (res) => router.push(res.outfit_id ? `/try?outfit=${res.outfit_id}` : `/try?product=${res.product_id}`),
  });

  return (
    <section data-index={index} className="relative flex tu-screen-h snap-start snap-always items-center justify-center overflow-hidden">
      {/* the picture or video, as big as the screen allows */}
      <div className="relative h-full w-full max-w-[min(calc(100vw/var(--page-zoom)),calc(56.25dvh/var(--page-zoom)))]" onClick={isVideo || p.music ? onToggleMute : undefined}>
        {isVideo ? (
          <video
            ref={video}
            src={near ? resolveMediaUrl(p.video_url) : undefined}
            poster={p.poster_url ? resolveMediaUrl(p.poster_url) : undefined}
            loop
            playsInline
            muted={muted || !!p.music}
            preload={near ? "auto" : "none"}
            className="absolute inset-0 h-full w-full object-contain"
          />
        ) : (
          p.image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={resolveMediaUrl(p.image_url)} alt={p.caption || `A post by @${p.author.handle}`} loading={near ? "eager" : "lazy"} className="absolute inset-0 h-full w-full object-contain" />
          )
        )}
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t from-black/75 to-transparent" />

      {/* actions, on the right */}
      <div className="absolute bottom-24 right-3 z-10 flex flex-col items-center gap-5 sm:right-[max(12px,calc(50%-min(calc(50vw/var(--page-zoom)),calc(28.125dvh/var(--page-zoom)))-72px))]">
        <Link href={`/u/${p.author.handle}`} aria-label={`@${p.author.handle}`} className="rounded-full ring-2 ring-white">
          <Avatar name={p.author.name} handle={p.author.handle} url={p.author.avatar_url} size={46} />
        </Link>
        <ReelAction
          label={p.liked_by_me ? "Liked" : "Like"}
          count={p.like_count}
          onClick={() => !like.isPending && like.mutate(!p.liked_by_me)}
          pressed={p.liked_by_me}
        >
          <span className={p.liked_by_me ? "text-[#ff5a4e]" : ""}>
            <HeartIcon filled={p.liked_by_me} size={30} />
          </span>
        </ReelAction>
        <ReelAction label="Comments" count={p.comment_count} onClick={onComments}>
          <span className="[&_svg]:h-[28px] [&_svg]:w-[28px]">
            <CommentIcon />
          </span>
        </ReelAction>
        {canTry && (
          <ReelAction label={tryIt.isPending ? "Opening…" : "Try it on"} onClick={() => tryIt.mutate()} highlight>
            <span className="[&_svg]:h-[34px] [&_svg]:w-[34px]">
              <HangerIcon />
            </span>
          </ReelAction>
        )}
      </div>

      {/* who posted it, the caption, the products */}
      <div className="absolute inset-x-0 bottom-0 z-10 px-4 pb-6 pr-20 sm:mx-auto sm:max-w-[min(calc(100vw/var(--page-zoom)),calc(56.25dvh/var(--page-zoom)))] sm:pr-4">
        <Link href={`/u/${p.author.handle}`} className="text-[16px] font-semibold drop-shadow">
          @{p.author.handle}
        </Link>
        {p.caption && (
          <button type="button" onClick={() => setExpanded((v) => !v)} className={`mt-1 block text-left text-[15px] leading-snug text-white/95 drop-shadow ${expanded ? "" : "line-clamp-2"}`}>
            {p.caption}
          </button>
        )}
        {p.music && (
          <button
            type="button"
            onClick={onToggleMute}
            aria-label={muted ? `Play the song: ${p.music.title}` : "Turn the sound off"}
            className="mt-2 flex max-w-[260px] items-center gap-2 rounded-full bg-white/15 py-1.5 pl-2.5 pr-3 text-[13.5px] backdrop-blur"
          >
            <SongLabel track={p.music} className="flex-1" />
            {muted && <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11.5px] font-bold text-black">Tap for sound</span>}
          </button>
        )}
        {p.products.length > 0 && (
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]">
            {p.products.map((prod) => (
              <a
                key={prod.id}
                href={prod.buy_url}
                target="_blank"
                rel="noopener sponsored"
                className="flex shrink-0 items-center gap-2 rounded-full bg-white/15 py-1 pl-1 pr-3 text-[13px] backdrop-blur hover:bg-white/25"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={resolveMediaUrl(prod.image_url)} alt="" className="h-8 w-8 rounded-full bg-white object-contain" />
                <span className="max-w-[140px] truncate">{prod.name}</span>
                {prod.price_cents > 0 && <span className="font-semibold">{formatPrice(prod.price_cents, prod.currency)}</span>}
              </a>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function ReelAction({
  children,
  label,
  count,
  onClick,
  pressed,
  highlight = false,
}: {
  children: React.ReactNode;
  label: string;
  count?: number;
  onClick: () => void;
  pressed?: boolean;
  highlight?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      aria-label={label}
      className={`flex flex-col items-center gap-1 font-semibold drop-shadow ${highlight ? "text-[15px]" : "text-[12.5px]"}`}
    >
      <span
        className={`grid place-items-center rounded-full ${
          highlight ? "tu-attention h-[68px] w-[68px] bg-sage text-white ring-2 ring-white/70" : "h-12 w-12 bg-white/15 backdrop-blur"
        }`}
      >
        {children}
      </span>
      {count !== undefined ? count : label}
    </button>
  );
}

function SpeakerIcon({ muted }: { muted: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M11 5 6 9H3v6h3l5 4V5z" />
      {muted ? <path d="m22 9-6 6M16 9l6 6" /> : <path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />}
    </svg>
  );
}
