"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { formatPrice } from "@/components/try/shop";
import { ApiError, relayedImageUrl, resolveMediaUrl } from "@/lib/api/client";
import { community, type CommunityComment, type CommunityPost } from "@/lib/api/endpoints";

export function timeAgo(iso: string): string {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  if (d < 7) return `${d}d`;
  return new Date(iso).toLocaleDateString();
}

export function Avatar({ name, handle, url, size = 40 }: { name: string | null; handle: string; url?: string | null; size?: number }) {
  const letter = (name || handle || "?").trim().charAt(0).toUpperCase();
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={resolveMediaUrl(url)} alt="" width={size} height={size} className="shrink-0 rounded-full object-cover" style={{ width: size, height: size }} />
  ) : (
    <span
      aria-hidden="true"
      className="grid shrink-0 place-items-center rounded-full bg-sage font-semibold text-white"
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {letter}
    </span>
  );
}

/** One look in the community: who posted it, the picture, the products, and
 * like / comment / try it on yourself. */
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
  const update = (next: CommunityPost) => {
    setP(next);
    onChange?.(next);
  };

  const like = useMutation({
    mutationFn: () => (p.liked_by_me ? community.unlike(p.id) : community.like(p.id)),
    onMutate: () => update({ ...p, liked_by_me: !p.liked_by_me, like_count: p.like_count + (p.liked_by_me ? -1 : 1) }),
    onSuccess: (res) => update({ ...p, liked_by_me: res.liked, like_count: res.like_count }),
  });
  const follow = useMutation({
    mutationFn: () => community.follow(p.author.handle),
    onSuccess: () => {
      update({ ...p, following_author: true });
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

      {image && (
        <Link href={`/community/post/${p.id}`} className="block bg-paper-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image} alt={p.caption || `A look by @${p.author.handle}`} loading="lazy" className="mx-auto max-h-[720px] w-full object-contain" />
        </Link>
      )}

      <div className="px-4 pb-4 pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => like.mutate()}
            aria-pressed={p.liked_by_me}
            className={`tu-press inline-flex min-h-[40px] items-center gap-1.5 rounded-full border px-3.5 text-[14.5px] font-semibold ${
              p.liked_by_me ? "border-[#c0503a]/40 bg-[#c0503a]/10 text-[#c0503a]" : "border-line text-ink hover:border-line-strong"
            }`}
          >
            <span aria-hidden="true">{p.liked_by_me ? "♥" : "♡"}</span> {p.like_count}
            <span className="sr-only">likes</span>
          </button>
          <button
            type="button"
            onClick={() => setShowComments((v) => !v)}
            className="tu-press inline-flex min-h-[40px] items-center gap-1.5 rounded-full border border-line px-3.5 text-[14.5px] font-semibold text-ink hover:border-line-strong"
          >
            <span aria-hidden="true">💬</span> {p.comment_count}
            <span className="sr-only">comments</span>
          </button>
          <button
            type="button"
            onClick={() => tryIt.mutate()}
            disabled={tryIt.isPending}
            className="tu-press ml-auto inline-flex min-h-[40px] items-center rounded-full bg-sage px-4 text-[14.5px] font-semibold text-white hover:bg-sage-deep"
          >
            {tryIt.isPending ? "Getting it ready…" : p.is_mine ? "Try again" : "Try this look"}
          </button>
        </div>
        {tryIt.isError && <p className="mt-2 text-[14px] text-[#a4553f]">{tryIt.error instanceof ApiError ? tryIt.error.detail : "Couldn't open this look."}</p>}
        {notice && <p className="mt-2 rounded-xl bg-sage-tint/40 px-3 py-2 text-[14px] text-ink">{notice}</p>}

        {p.caption && (
          <p className="mt-3 whitespace-pre-wrap text-[15.5px] leading-relaxed text-ink">
            <Link href={`/u/${p.author.handle}`} className="font-semibold">@{p.author.handle}</Link> {p.caption}
          </p>
        )}

        {p.products.length > 0 && (
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
            {p.products.map((prod) => (
              <a
                key={prod.id}
                href={prod.buy_url}
                target="_blank"
                rel="noopener sponsored"
                className="flex w-[150px] shrink-0 items-center gap-2 rounded-xl border border-line p-1.5 hover:border-line-strong"
                title={prod.name}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={relayedImageUrl(prod.image_url, 200)} alt="" loading="lazy" className="h-11 w-11 shrink-0 rounded-lg bg-white object-contain" />
                <span className="min-w-0">
                  <span className="block truncate text-[12.5px] text-ink">{prod.name}</span>
                  <span className="block text-[12px] font-semibold text-sage-deep">
                    {prod.price_cents > 0 ? formatPrice(prod.price_cents, prod.currency) : "Shop"} →
                  </span>
                </span>
              </a>
            ))}
          </div>
        )}

        {showComments && <Comments post={p} onCount={(n) => update({ ...p, comment_count: n })} />}
      </div>
    </article>
  );
}

function Comments({ post, onCount }: { post: CommunityPost; onCount: (n: number) => void }) {
  const qc = useQueryClient();
  const key = ["community", "comments", post.id];
  const list = useQuery({ queryKey: key, queryFn: () => community.comments(post.id) });
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState<CommunityComment | null>(null);
  const [reported, setReported] = useState<string[]>([]);
  const count = (items: CommunityComment[]) => items.reduce((n, c) => n + 1 + c.replies.length, 0);
  const add = useMutation({
    mutationFn: () => community.comment(post.id, text.trim(), replyTo?.id),
    onSuccess: async () => {
      setText("");
      setReplyTo(null);
      const fresh = await qc.fetchQuery({ queryKey: key, queryFn: () => community.comments(post.id) });
      onCount(count(fresh));
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => community.removeComment(id),
    onSuccess: async () => {
      const fresh = await qc.fetchQuery({ queryKey: key, queryFn: () => community.comments(post.id) });
      onCount(count(fresh));
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) add.mutate();
  };

  const row = (c: CommunityComment, reply = false) => (
    <div key={c.id} className={`flex gap-2.5 ${reply ? "ml-10 mt-2" : "mt-3"}`}>
      <Link href={`/u/${c.author.handle}`}>
        <Avatar name={c.author.name} handle={c.author.handle} url={c.author.avatar_url} size={30} />
      </Link>
      <div className="min-w-0 flex-1">
        <div className="rounded-2xl bg-paper-2 px-3 py-2">
          <Link href={`/u/${c.author.handle}`} className="text-[13.5px] font-semibold text-ink">@{c.author.handle}</Link>
          <p className="whitespace-pre-wrap text-[14.5px] leading-snug text-ink">{c.body}</p>
        </div>
        <div className="mt-1 flex gap-3 pl-2 text-[12.5px] text-muted">
          <span>{timeAgo(c.created_at)}</span>
          <button type="button" onClick={() => setReplyTo(c)} className="font-semibold hover:text-ink">Reply</button>
          {c.can_delete && (
            <button type="button" onClick={() => remove.mutate(c.id)} className="hover:text-[#a4553f]">Delete</button>
          )}
          {!c.is_mine &&
            (reported.includes(c.id) ? (
              <span>Reported ✓</span>
            ) : (
              <button
                type="button"
                onClick={() => community.report({ comment_id: c.id, reason: "Comment reported" }).then(() => setReported((r) => [...r, c.id]))}
                className="hover:text-ink"
              >
                Report
              </button>
            ))}
        </div>
        {c.replies.map((r) => row(r, true))}
      </div>
    </div>
  );

  return (
    <div className="mt-4 border-t border-line pt-2">
      {list.isLoading && <p className="mt-3 text-[14px] text-muted">Loading comments…</p>}
      {list.data && list.data.length === 0 && <p className="mt-3 text-[14px] text-muted">No comments yet. Be the first!</p>}
      {list.data?.map((c) => row(c))}
      <form onSubmit={submit} className="mt-4">
        {replyTo && (
          <p className="mb-1.5 text-[13px] text-muted">
            Replying to @{replyTo.author.handle}{" "}
            <button type="button" onClick={() => setReplyTo(null)} className="font-semibold text-ink">Cancel</button>
          </p>
        )}
        <div className="flex gap-2">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={1000}
            placeholder={replyTo ? "Write a reply…" : "Add a kind comment…"}
            aria-label="Comment"
            className="h-11 min-w-0 flex-1 rounded-full border border-line-strong bg-paper px-4 text-[15px] text-ink"
          />
          <button
            type="submit"
            disabled={!text.trim() || add.isPending}
            className="tu-press min-h-[44px] shrink-0 rounded-full bg-sage px-4 text-[14.5px] font-semibold text-white disabled:opacity-50"
          >
            Post
          </button>
        </div>
        {add.isError && <p className="mt-2 text-[14px] text-[#a4553f]">{add.error instanceof ApiError ? add.error.detail : "Couldn't post your comment."}</p>}
      </form>
    </div>
  );
}
