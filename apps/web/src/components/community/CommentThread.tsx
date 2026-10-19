"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Avatar, HangerIcon, LinkCards, PhotoIcon, ProductChips, RichText, ThumbIcon, timeAgo } from "@/components/community/parts";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { community, type CommunityComment, type CommunityPost } from "@/lib/api/endpoints";

/** replies move in under their comment this many times; deeper ones stay in line, with the @name they answer */
const MAX_INDENT = 3;

type Ctx = { postId: string; refresh: () => Promise<void> };

const countAll = (items: CommunityComment[]): number => items.reduce((n, c) => n + 1 + countAll(c.replies), 0);

/** The conversation under a post, like Facebook and LinkedIn: comments,
 * replies to replies, likes, photos, looks, and TryOnU links with a preview. */
export function Comments({ post, onCount }: { post: CommunityPost; onCount: (n: number) => void }) {
  const qc = useQueryClient();
  const key = ["community", "comments", post.id];
  const list = useQuery({ queryKey: key, queryFn: () => community.comments(post.id) });
  const ctx: Ctx = {
    postId: post.id,
    refresh: async () => {
      // staleTime 0: the app keeps data a minute by default, and a new comment must show at once
      const fresh = await qc.fetchQuery({ queryKey: key, queryFn: () => community.comments(post.id), staleTime: 0 });
      onCount(countAll(fresh));
    },
  };
  return (
    <div className="mt-3 border-t border-line pt-3">
      <CommentComposer ctx={ctx} />
      {list.isLoading && <p className="mt-4 text-[14px] text-muted">Loading comments…</p>}
      {list.data && list.data.length === 0 && <p className="mt-4 text-[14px] text-muted">No comments yet. Be the first!</p>}
      <div className="mt-4 space-y-4">
        {list.data?.map((c) => (
          <CommentItem key={c.id} c={c} depth={0} ctx={ctx} />
        ))}
      </div>
    </div>
  );
}

function CommentItem({ c, depth, ctx }: { c: CommunityComment; depth: number; ctx: Ctx }) {
  const router = useRouter();
  const [liked, setLiked] = useState({ on: c.liked_by_me, n: c.like_count });
  const [replying, setReplying] = useState(false);
  const total = countAll(c.replies);
  const [open, setOpen] = useState(total <= 2);
  const [reported, setReported] = useState(false);

  const like = useMutation({
    mutationFn: (want: boolean) => (want ? community.likeComment(c.id) : community.unlikeComment(c.id)),
    onMutate: (want: boolean) => setLiked((prev) => ({ on: want, n: Math.max(0, prev.n + (want ? 1 : -1)) })),
    onSuccess: (res) => setLiked({ on: res.liked, n: res.like_count }),
    onError: (_e, want) => setLiked((prev) => ({ on: !want, n: Math.max(0, prev.n + (want ? -1 : 1)) })),
  });
  const remove = useMutation({ mutationFn: () => community.removeComment(c.id), onSuccess: () => ctx.refresh() });
  const tryIt = useMutation({
    mutationFn: () => community.tryCommentLook(c.id),
    onSuccess: (res) => router.push(res.outfit_id ? `/try?outfit=${res.outfit_id}` : `/try?product=${res.product_id}`),
  });

  const small = depth > 0;
  const replies = c.replies.map((r) => <CommentItem key={r.id} c={r} depth={depth + 1} ctx={ctx} />);
  return (
    <div>
      <div className="flex gap-2.5">
        <Link href={`/u/${c.author.handle}`} className="shrink-0" aria-label={`@${c.author.handle}`}>
          <Avatar name={c.author.name} handle={c.author.handle} url={c.author.avatar_url} size={small ? 28 : 34} />
        </Link>
        <div className="min-w-0 flex-1">
          {(c.body || c.previews.length > 0) && (
            <div className="inline-block max-w-full rounded-2xl bg-paper-2 px-3.5 py-2.5">
              <p className="flex flex-wrap items-baseline gap-x-1.5">
                <Link href={`/u/${c.author.handle}`} className="text-[14px] font-semibold text-ink hover:underline">
                  {c.author.name || `@${c.author.handle}`}
                </Link>
                {c.author.name && <span className="text-[12.5px] text-muted">@{c.author.handle}</span>}
              </p>
              {c.body && (
                <p className="mt-0.5 whitespace-pre-wrap break-words text-[14.5px] leading-snug text-ink">
                  <RichText text={c.body} mention={depth >= 2 ? c.reply_to : null} />
                </p>
              )}
              <LinkCards previews={c.previews} />
            </div>
          )}
          {!c.body && c.previews.length === 0 && (
            <Link href={`/u/${c.author.handle}`} className="text-[14px] font-semibold text-ink hover:underline">
              {c.author.name || `@${c.author.handle}`}
            </Link>
          )}

          {c.image_url && (
            <a href={resolveMediaUrl(c.image_url)} target="_blank" rel="noopener" className="mt-1.5 block w-fit">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={resolveMediaUrl(c.image_url)} alt={`A photo by @${c.author.handle}`} loading="lazy" className="max-h-72 max-w-full rounded-xl border border-line object-contain" />
            </a>
          )}

          {c.look && (
            <div className="mt-1.5 max-w-[440px] rounded-xl border border-line bg-surface p-2">
              <div className="flex gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={resolveMediaUrl(c.look.image_url)} alt={`A look by @${c.author.handle}`} loading="lazy" className="h-36 w-28 shrink-0 rounded-lg bg-paper-2 object-cover object-top" />
                <div className="flex min-w-0 flex-1 flex-col">
                  <p className="text-[13.5px] font-semibold text-ink">@{c.author.handle}&apos;s look</p>
                  <p className="text-[12.5px] text-muted">
                    {c.look.products.length} {c.look.products.length === 1 ? "product" : "products"}
                  </p>
                  <button
                    type="button"
                    onClick={() => tryIt.mutate()}
                    disabled={tryIt.isPending}
                    className="tu-press tu-attention mt-auto inline-flex min-h-[40px] w-fit items-center gap-1.5 rounded-full bg-sage-tint/50 px-3.5 text-[13.5px] font-semibold text-sage-deep"
                  >
                    <HangerIcon size={17} />
                    {tryIt.isPending ? "Opening…" : "Try it on"}
                  </button>
                </div>
              </div>
              <ProductChips products={c.look.products} className="mt-2" />
              {tryIt.isError && <p className="mt-1 text-[13px] text-[#a4553f]">{tryIt.error instanceof ApiError ? tryIt.error.detail : "Couldn't open this look."}</p>}
            </div>
          )}

          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 pl-1 text-[13px] text-muted">
            <span>{timeAgo(c.created_at)}</span>
            <button
              type="button"
              aria-pressed={liked.on}
              onClick={() => !like.isPending && like.mutate(!liked.on)}
              className={`font-semibold hover:underline ${liked.on ? "text-sage-deep" : "hover:text-ink"}`}
            >
              {liked.on ? "Liked" : "Like"}
            </button>
            {liked.n > 0 && (
              <span className="inline-flex items-center gap-1" aria-label={`${liked.n} likes`}>
                <span className="grid h-[17px] w-[17px] place-items-center rounded-full bg-sage-deep text-white">
                  <ThumbIcon filled size={10} />
                </span>
                {liked.n}
              </span>
            )}
            <span aria-hidden="true" className="text-line-strong">|</span>
            <button type="button" onClick={() => setReplying((v) => !v)} className="font-semibold hover:text-ink hover:underline">
              Reply
            </button>
            {c.can_delete && (
              <button
                type="button"
                onClick={() => window.confirm("Delete this comment and the replies under it?") && remove.mutate()}
                className="hover:text-[#a4553f]"
              >
                Delete
              </button>
            )}
            {!c.is_mine &&
              (reported ? (
                <span>Reported</span>
              ) : (
                <button
                  type="button"
                  onClick={() => community.report({ comment_id: c.id, reason: "Comment reported" }).then(() => setReported(true))}
                  className="hover:text-ink"
                >
                  Report
                </button>
              ))}
          </div>

          {replying && (
            <div className="mt-2">
              <CommentComposer
                ctx={ctx}
                parent={c}
                autoFocus
                onDone={() => {
                  setReplying(false);
                  setOpen(true);
                }}
              />
            </div>
          )}
        </div>
      </div>

      {total > 0 &&
        (open ? (
          depth < MAX_INDENT - 1 ? (
            <div className={`mt-3 space-y-3 border-l-2 border-line pl-3 ${small ? "ml-[13px]" : "ml-[16px]"}`}>{replies}</div>
          ) : (
            <div className="mt-3 space-y-3">{replies}</div>
          )
        ) : (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className={`mt-2 flex items-center gap-2 text-[13.5px] font-semibold text-ink-soft hover:text-ink ${small ? "ml-[38px]" : "ml-[44px]"}`}
          >
            <span aria-hidden="true" className="h-px w-6 bg-line-strong" />
            View {total} {total === 1 ? "reply" : "replies"}
          </button>
        ))}
    </div>
  );
}

type MyLook = { job_id: string; image_url: string };

/** Write a comment or a reply: text, a photo, or one of my looks. */
function CommentComposer({
  ctx,
  parent,
  autoFocus = false,
  onDone,
}: {
  ctx: Ctx;
  parent?: CommunityComment;
  autoFocus?: boolean;
  onDone?: () => void;
}) {
  const me = useQuery({ queryKey: ["community", "me"], queryFn: community.me });
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<{ key: string; url: string } | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [look, setLook] = useState<MyLook | null>(null);
  const [picking, setPicking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const looks = useQuery({ queryKey: ["community", "my-looks"], queryFn: community.myLooks, enabled: picking });
  // "@sa" just typed: suggest members to mention
  const [mentioning, setMentioning] = useState<string | null>(null);
  const people = useQuery({
    queryKey: ["community", "people", mentioning],
    queryFn: () => community.people(mentioning ?? ""),
    enabled: mentioning !== null,
    staleTime: 30_000,
  });
  const watchMention = (value: string, caret: number) => {
    const m = value.slice(0, caret).match(/(?:^|\s)@([A-Za-z0-9_.]{0,30})$/);
    setMentioning(m ? m[1] : null);
  };
  const pickMention = (handle: string) => {
    const el = box.current;
    const caret = el?.selectionStart ?? text.length;
    const before = text.slice(0, caret).replace(/@([A-Za-z0-9_.]{0,30})$/, `@${handle} `);
    const next = before + text.slice(caret);
    setText(next);
    setMentioning(null);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(before.length, before.length);
    });
  };

  useEffect(() => {
    if (autoFocus) box.current?.focus();
  }, [autoFocus]);
  const grow = () => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  };

  const upload = async (file: File) => {
    setError(null);
    if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) {
      setError("Please choose a photo.");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError("That photo is too big. Please use one under 15 MB.");
      return;
    }
    setProgress(0);
    try {
      const res = await community.commentImage(file, setProgress);
      setPhoto({ key: res.image_key, url: res.image_url });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't add that photo.");
    } finally {
      setProgress(null);
    }
  };

  const send = useMutation({
    mutationFn: () =>
      community.comment(ctx.postId, {
        body: text.trim(),
        parent_id: parent?.id,
        image_key: photo?.key,
        tryon_job_id: look?.job_id,
      }),
    onSuccess: async (res) => {
      setText("");
      setPhoto(null);
      setLook(null);
      setPicking(false);
      setError(null);
      if (box.current) box.current.style.height = "auto";
      setNotice(
        res.links_removed
          ? `We took out ${res.links_removed === 1 ? "a link" : `${res.links_removed} links`} to another website. Only TryOnU store and product links can be shared.`
          : null,
      );
      await ctx.refresh();
      onDone?.();
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : "Couldn't post your comment."),
  });
  const ready = (text.trim() || photo || look) && progress === null && !send.isPending;
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (ready) send.mutate();
  };

  return (
    <form onSubmit={submit} className="flex gap-2.5">
      {me.data && <Avatar name={me.data.name} handle={me.data.handle} url={me.data.avatar_url} size={parent ? 28 : 34} />}
      <div className="min-w-0 flex-1">
        <div className="rounded-[20px] border border-line-strong bg-paper focus-within:border-sage focus-within:ring-2 focus-within:ring-sage/20">
          <textarea
            ref={box}
            value={text}
            rows={1}
            maxLength={1000}
            onChange={(e) => {
              setText(e.target.value);
              watchMention(e.target.value, e.target.selectionStart ?? e.target.value.length);
              grow();
            }}
            onKeyDown={(e) => {
              if (mentioning !== null && people.data?.length && (e.key === "Enter" || e.key === "Tab")) {
                e.preventDefault();
                pickMention(people.data[0].handle);
                return;
              }
              if (e.key === "Escape") setMentioning(null);
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit();
            }}
            onBlur={() => setTimeout(() => setMentioning(null), 150)}
            placeholder={parent ? `Reply to @${parent.author.handle}…` : "Add a comment… (type @ to mention someone)"}
            aria-label={parent ? `Reply to @${parent.author.handle}` : "Add a comment"}
            className="block w-full resize-none bg-transparent px-4 pt-2.5 text-[15px] leading-snug text-ink outline-none placeholder:text-faint"
          />

          {mentioning !== null && (people.data?.length ?? 0) > 0 && (
            <div className="mx-2 mt-1 overflow-hidden rounded-xl border border-line bg-surface shadow-lift" role="listbox" aria-label="Mention someone">
              {people.data!.slice(0, 6).map((p, i) => (
                <button
                  key={p.handle}
                  type="button"
                  role="option"
                  aria-selected={i === 0}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    pickMention(p.handle);
                  }}
                  className={`flex w-full items-center gap-2.5 px-3 py-2 text-left hover:bg-paper-2 ${i === 0 ? "bg-paper-2/60" : ""}`}
                >
                  <Avatar name={p.name} handle={p.handle} url={p.avatar_url} size={26} />
                  <span className="min-w-0">
                    <span className="block truncate text-[14px] font-semibold text-ink">{p.name || `@${p.handle}`}</span>
                    <span className="block truncate text-[12.5px] text-muted">@{p.handle}</span>
                  </span>
                </button>
              ))}
            </div>
          )}

          {(photo || progress !== null || look) && (
            <div className="flex flex-wrap gap-2 px-3 pt-2">
              {progress !== null && (
                <div className="grid h-20 w-20 place-items-center rounded-xl bg-paper-2 text-[12.5px] font-semibold text-muted">{progress}%</div>
              )}
              {photo && (
                <Attachment label="Remove photo" onRemove={() => setPhoto(null)}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={resolveMediaUrl(photo.url)} alt="Your photo" className="h-20 w-20 rounded-xl object-cover" />
                </Attachment>
              )}
              {look && (
                <Attachment label="Remove look" onRemove={() => setLook(null)}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={resolveMediaUrl(look.image_url)} alt="Your look" className="h-20 w-16 rounded-xl object-cover object-top" />
                </Attachment>
              )}
            </div>
          )}

          <div className="flex items-center gap-1 px-2 pb-1.5 pt-1">
            <label
              className="grid h-9 w-9 cursor-pointer place-items-center rounded-full text-ink-soft hover:bg-paper-2 hover:text-ink"
              title="Add a photo"
            >
              <input
                type="file"
                accept="image/*,.heic,.heif"
                className="sr-only"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) upload(file);
                  e.target.value = "";
                }}
              />
              <PhotoIcon />
              <span className="sr-only">Add a photo</span>
            </label>
            <button
              type="button"
              onClick={() => setPicking((v) => !v)}
              aria-expanded={picking}
              title="Add one of your looks"
              className={`flex h-9 items-center gap-1.5 rounded-full px-2.5 text-[13.5px] font-semibold hover:bg-paper-2 ${picking ? "text-ink" : "text-ink-soft hover:text-ink"}`}
            >
              <HangerIcon size={19} />
              <span className="hidden sm:inline">Add a look</span>
            </button>
            <span className="flex-1" />
            {parent && onDone && (
              <button type="button" onClick={onDone} className="min-h-[36px] rounded-full px-3 text-[13.5px] font-semibold text-muted hover:text-ink">
                Cancel
              </button>
            )}
            <button
              type="submit"
              disabled={!ready}
              className="tu-press min-h-[36px] rounded-full bg-sage px-4 text-[14px] font-semibold text-white disabled:opacity-40"
            >
              {send.isPending ? "Posting…" : parent ? "Reply" : "Post"}
            </button>
          </div>
        </div>

        {picking && (
          <div className="mt-2 rounded-[16px] border border-line bg-surface p-3">
            <p className="text-[13.5px] font-semibold text-ink">Add one of your looks</p>
            {looks.isLoading && <p className="mt-2 text-[13.5px] text-muted">Loading your looks…</p>}
            {looks.data && looks.data.length === 0 && (
              <p className="mt-2 text-[13.5px] text-muted">
                No looks yet.{" "}
                <Link href="/try" className="font-semibold text-sage-deep hover:underline">
                  Make one on Try on →
                </Link>
              </p>
            )}
            {looks.data && looks.data.length > 0 && (
              <div className="mt-2 grid grid-cols-4 gap-2 sm:grid-cols-6">
                {looks.data.map((l) => (
                  <button
                    key={l.job_id}
                    type="button"
                    onClick={() => {
                      setLook({ job_id: l.job_id, image_url: l.image_url });
                      setPicking(false);
                    }}
                    className={`overflow-hidden rounded-lg border-2 ${look?.job_id === l.job_id ? "border-sage" : "border-transparent hover:border-line-strong"}`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={resolveMediaUrl(l.image_url)} alt="One of your looks" loading="lazy" className="aspect-[3/4] w-full bg-paper-2 object-cover object-top" />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {error && <p className="mt-1.5 text-[13.5px] text-[#a4553f]">{error}</p>}
        {notice && <p className="mt-1.5 rounded-lg bg-[#c9a13b]/10 px-3 py-2 text-[13.5px] text-[#8a6d1f]">{notice}</p>}
      </div>
    </form>
  );
}

function Attachment({ children, label, onRemove }: { children: React.ReactNode; label: string; onRemove: () => void }) {
  return (
    <span className="relative">
      {children}
      <button
        type="button"
        onClick={onRemove}
        aria-label={label}
        className="absolute -right-1.5 -top-1.5 grid h-6 w-6 place-items-center rounded-full bg-ink text-[14px] leading-none text-surface"
      >
        ×
      </button>
    </span>
  );
}
