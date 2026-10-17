"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { community } from "@/lib/api/endpoints";

export const COMMUNITY_RULES = [
  "Post only looks made with your own photo.",
  "Be kind: no insults, hate or harassment.",
  "No nudity or anything unsafe for all ages.",
  "No spam or advertising in comments.",
];

/** "Post to community" for a finished look: a caption, the rules, and Post. */
export function PostToCommunity({ jobId, imageUrl }: { jobId: string; imageUrl?: string | null }) {
  const [open, setOpen] = useState(false);
  const [caption, setCaption] = useState("");
  const [agree, setAgree] = useState(false);
  const existing = useQuery({ queryKey: ["community", "by-job", jobId], queryFn: () => community.postForJob(jobId) });
  const post = useMutation({
    mutationFn: () => community.create({ tryon_job_id: jobId, caption: caption.trim() || undefined, accept_rules: agree }),
    onSuccess: () => existing.refetch(),
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const postId = post.data?.id ?? existing.data?.post_id ?? null;
  if (postId && !open) {
    return (
      <Link
        href={`/community/post/${postId}`}
        className="flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full border border-line-strong bg-surface px-5 text-[15.5px] font-semibold text-ink hover:border-ink/40"
      >
        ✓ In the community · View post
      </Link>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="tu-press flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full border border-line-strong bg-surface px-5 text-[15.5px] font-semibold text-ink hover:border-ink/40"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="9" cy="8" r="3.5" />
          <path d="M2.5 20c.6-3.5 3.3-5.5 6.5-5.5s5.9 2 6.5 5.5" />
          <path d="M16 4.8a3.3 3.3 0 0 1 0 6.4M18.5 14.7c1.6.8 2.7 2.6 3 5.3" />
        </svg>
        Post to community
      </button>
      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
            onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
          >
            <div role="dialog" aria-modal="true" aria-label="Post to community" className="w-full max-w-[480px] rounded-t-[20px] border border-line bg-surface p-5 sm:rounded-[20px] sm:p-6">
              {post.isSuccess ? (
                <div className="py-4 text-center">
                  <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-sage text-[26px] text-white">✓</div>
                  <p className="mt-4 text-[19px] font-semibold text-ink">Posted to the community</p>
                  <p className="mt-1 text-[15px] text-muted">Members can now like it, comment and try your look.</p>
                  <div className="mt-5 flex flex-wrap justify-center gap-3">
                    <Link href={`/community/post/${post.data.id}`} className="inline-flex min-h-[44px] items-center rounded-full bg-sage px-5 text-[15px] font-semibold text-white">
                      View my post
                    </Link>
                    <button type="button" onClick={() => setOpen(false)} className="min-h-[44px] rounded-full border border-line-strong px-5 text-[15px] font-semibold text-ink">
                      Close
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <h2 className="text-[19px] font-semibold text-ink">Post to the TryOnU community</h2>
                  <p className="mt-1 text-[14.5px] text-muted">Members can see this look, like it, comment and try it on themselves. You can delete it any time.</p>
                  <div className="mt-4 flex gap-3">
                    {imageUrl && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={resolveMediaUrl(imageUrl)} alt="" className="h-28 w-24 shrink-0 rounded-xl bg-paper-2 object-cover object-top" />
                    )}
                    <textarea
                      value={caption}
                      onChange={(e) => setCaption(e.target.value)}
                      maxLength={1000}
                      rows={4}
                      placeholder="Say something about this look… (optional)"
                      aria-label="Caption"
                      className="min-w-0 flex-1 rounded-xl border border-line-strong bg-paper p-3 text-[15px] text-ink"
                    />
                  </div>
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
                    <button type="button" onClick={() => setOpen(false)} className="min-h-[46px] flex-1 rounded-full border border-line-strong text-[15px] font-semibold text-ink">
                      Cancel
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
              )}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
