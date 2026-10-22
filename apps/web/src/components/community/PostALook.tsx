"use client";

import { CheckIcon } from "@/components/ui/Icons";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { PostOptions } from "@/components/community/extras";
import { COMMUNITY_RULES } from "@/components/community/PostToCommunity";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { community, type PostExtras } from "@/lib/api/endpoints";

/** "Post a look" on the community page: pick one of my finished looks (saved
 * ones first), add a caption, post. No looks yet: make one first. */
export function PostALook({
  variant = "primary",
  startOpen = false,
  onClosed,
  extras: startExtras = {},
}: {
  variant?: "primary" | "wide" | "none";
  /** opened from the Create post chooser: no button of its own */
  startOpen?: boolean;
  onClosed?: () => void;
  /** e.g. opened from "Join the challenge": that challenge already ticked */
  extras?: PostExtras;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(startOpen);
  const [chosen, setChosen] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [agree, setAgree] = useState(false);
  const [extras, setExtras] = useState<PostExtras>(startExtras);
  const looks = useQuery({ queryKey: ["community", "my-looks"], queryFn: community.myLooks, enabled: open });
  const post = useMutation({
    mutationFn: () => community.create({ tryon_job_id: chosen!, caption: caption.trim() || undefined, accept_rules: agree, ...extras }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["community"] });
    },
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const close = () => {
    setOpen(false);
    onClosed?.();
    setChosen(null);
    setCaption("");
    setAgree(false);
    post.reset();
  };
  const picked = looks.data?.find((l) => l.job_id === chosen) ?? null;
  const available = (looks.data ?? []).filter((l) => !l.post_id);

  const trigger =
    variant === "wide" ? (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="tu-press flex min-h-[48px] w-full items-center justify-center rounded-full bg-sage px-5 text-[15.5px] font-semibold text-white hover:bg-sage-deep"
      >
        ＋ Post a look
      </button>
    ) : (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="tu-press inline-flex min-h-[44px] items-center rounded-full bg-sage px-5 text-[15px] font-semibold text-white hover:bg-sage-deep"
      >
        ＋ Post a look
      </button>
    );

  return (
    <>
      {variant !== "none" && trigger}
      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
            onMouseDown={(e) => e.target === e.currentTarget && close()}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Post a look"
              className="flex max-h-[92vh] w-full max-w-[620px] flex-col rounded-t-[20px] border border-line bg-surface sm:rounded-[20px]"
            >
              <div className="flex items-center justify-between border-b border-line px-5 py-4">
                <h2 className="text-[18px] font-semibold text-ink">
                  {post.isSuccess ? "Posted" : picked ? "Add a caption" : "Choose a look to post"}
                </h2>
                <button type="button" onClick={close} aria-label="Close" className="grid h-9 w-9 place-items-center rounded-lg text-[22px] text-muted hover:bg-paper-2 hover:text-ink">
                  ×
                </button>
              </div>

              <div className="overflow-y-auto p-5">
                {post.isSuccess ? (
                  <div className="py-6 text-center">
                    <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-sage text-[26px] text-white"><CheckIcon size={28} /></div>
                    <p className="mt-4 text-[18px] font-semibold text-ink">Your look is in the community</p>
                    <p className="mt-1 text-[15px] text-muted">Members can now like it, comment and try it on themselves.</p>
                    <div className="mt-5 flex flex-wrap justify-center gap-3">
                      <Link href={`/community/post/${post.data.id}`} onClick={close} className="inline-flex min-h-[44px] items-center rounded-full bg-sage px-5 text-[15px] font-semibold text-white">
                        View my post
                      </Link>
                      <button type="button" onClick={close} className="min-h-[44px] rounded-full border border-line-strong px-5 text-[15px] font-semibold text-ink">
                        Back to the feed
                      </button>
                    </div>
                  </div>
                ) : picked ? (
                  <>
                    <div className="flex gap-4">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={resolveMediaUrl(picked.image_url)} alt="" className="h-40 w-32 shrink-0 rounded-xl bg-paper-2 object-cover object-top" />
                      <textarea
                        value={caption}
                        onChange={(e) => setCaption(e.target.value)}
                        maxLength={1000}
                        rows={5}
                        placeholder="Say something about this look… (optional)"
                        aria-label="Caption"
                        className="min-w-0 flex-1 rounded-xl border border-line-strong bg-paper p-3 text-[15px] text-ink"
                      />
                    </div>
                    <PostOptions value={extras} onChange={setExtras} />
                    <div className="mt-4 rounded-xl bg-paper-2 p-3">
                      <p className="text-[13.5px] font-semibold text-ink">Community rules</p>
                      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13.5px] text-ink-soft">
                        {COMMUNITY_RULES.map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    </div>
                    <label className="mt-3 flex items-start gap-2.5 text-[14.5px] text-ink">
                      <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-1 h-4 w-4 accent-[#5f7a5b]" />
                      I agree to the community rules, and this look uses my own photo.
                    </label>
                    {post.isError && (
                      <p className="mt-3 text-[14px] text-[#a4553f]">{post.error instanceof ApiError ? post.error.detail : "Couldn't post. Please try again."}</p>
                    )}
                    <div className="mt-5 flex gap-3">
                      <button type="button" onClick={() => setChosen(null)} className="min-h-[46px] flex-1 rounded-full border border-line-strong text-[15px] font-semibold text-ink">
                        ← Choose another
                      </button>
                      <button
                        type="button"
                        disabled={!agree || post.isPending}
                        onClick={() => post.mutate()}
                        className="tu-press min-h-[46px] flex-1 rounded-full bg-sage text-[15px] font-semibold text-white disabled:opacity-50"
                      >
                        {post.isPending ? "Posting…" : "Post"}
                      </button>
                    </div>
                  </>
                ) : looks.isLoading ? (
                  <div className="grid grid-cols-3 gap-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <div key={i} className="aspect-[3/4] animate-pulse rounded-xl bg-paper-2" />
                    ))}
                  </div>
                ) : (looks.data ?? []).length === 0 ? (
                  <div className="py-6 text-center">
                    <p className="text-[17px] font-semibold text-ink">You don&apos;t have a look yet</p>
                    <p className="mx-auto mt-1 max-w-sm text-[15px] text-muted">
                      Make a try-on first: pick a product or an outfit, see it on you, then post it here.
                    </p>
                    <Link href="/try" onClick={close} className="mt-5 inline-flex min-h-[46px] items-center rounded-full bg-sage px-6 text-[15px] font-semibold text-white">
                      Make a look
                    </Link>
                  </div>
                ) : (
                  <>
                    <p className="text-[14.5px] text-muted">
                      {available.length > 0 ? "Tap a look to post it. Saved looks are shown first." : "You've posted all your looks. Make a new one!"}
                    </p>
                    <div className="mt-4 grid grid-cols-3 gap-3">
                      {(looks.data ?? []).map((l) => (
                        <button
                          key={l.job_id}
                          type="button"
                          disabled={!!l.post_id}
                          onClick={() => setChosen(l.job_id)}
                          className="group relative aspect-[3/4] overflow-hidden rounded-xl border border-line bg-paper-2 text-left disabled:cursor-default"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={resolveMediaUrl(l.image_url)}
                            alt=""
                            loading="lazy"
                            className={`h-full w-full object-cover object-top transition-transform ${l.post_id ? "opacity-50" : "group-hover:scale-[1.03]"}`}
                          />
                          {l.post_id ? (
                            <span className="absolute left-1.5 top-1.5 rounded-full bg-ink px-2 py-0.5 text-[11.5px] font-semibold text-surface">Posted</span>
                          ) : l.saved ? (
                            <span className="absolute left-1.5 top-1.5 rounded-full bg-sage px-2 py-0.5 text-[11.5px] font-semibold text-white">Saved</span>
                          ) : null}
                        </button>
                      ))}
                    </div>
                    <div className="mt-5 text-center">
                      <Link href="/try" onClick={close} className="text-[15px] font-semibold text-sage-deep hover:underline">
                        Or make a new look →
                      </Link>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
