"use client";

import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { PostALook } from "@/components/community/PostALook";
import { COMMUNITY_RULES } from "@/components/community/PostToCommunity";
import { ApiError } from "@/lib/api/client";
import { community, type CommunityPost } from "@/lib/api/endpoints";

const MAX_VIDEO_MB = 60;
const MAX_VIDEO_SECONDS = 60;
const MAX_PHOTO_MB = 12;

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);
  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className="flex max-h-[92vh] w-full max-w-[560px] flex-col rounded-t-[20px] border border-line bg-surface sm:rounded-[20px]">
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-[18px] font-semibold text-ink">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="grid h-9 w-9 place-items-center rounded-lg text-[22px] text-muted hover:bg-paper-2 hover:text-ink">
            ×
          </button>
        </div>
        <div className="overflow-y-auto p-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

/** "+ Create post": post a try-on look, or upload my own photo or video. */
export function CreatePost({ variant = "primary" }: { variant?: "primary" | "wide" }) {
  const [step, setStep] = useState<"closed" | "choose" | "look" | "media">("closed");
  const button =
    variant === "wide"
      ? "tu-press flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full bg-sage px-5 text-[15.5px] font-semibold text-white hover:bg-sage-deep"
      : "tu-press inline-flex min-h-[44px] items-center gap-2 rounded-full bg-sage px-5 text-[15px] font-semibold text-white hover:bg-sage-deep";
  return (
    <>
      <button type="button" onClick={() => setStep("choose")} className={button}>
        <span aria-hidden="true" className="text-[18px] leading-none">＋</span> Create post
      </button>
      {step === "choose" && (
        <Modal title="Create a post" onClose={() => setStep("closed")}>
          <div className="grid gap-3 sm:grid-cols-2">
            <ChoiceCard
              title="Post a try-on look"
              text="One of your saved looks or try-ons. Others can try the same products."
              onClick={() => setStep("look")}
              icon={
                <path d="M12 7.5a2 2 0 1 1 2-2M12 7.5v1.6L3.4 15.2a1.4 1.4 0 0 0 .8 2.5h15.6a1.4 1.4 0 0 0 .8-2.5L12 9.1" />
              }
            />
            <ChoiceCard
              title="Upload a photo or video"
              text={`From your phone or computer. Videos up to ${MAX_VIDEO_SECONDS} seconds.`}
              onClick={() => setStep("media")}
              icon={
                <>
                  <rect x="3" y="5" width="13" height="14" rx="2" />
                  <path d="m16 10 5-3v10l-5-3" />
                </>
              }
            />
          </div>
        </Modal>
      )}
      {step === "look" && <PostALook variant="none" startOpen onClosed={() => setStep("closed")} />}
      {step === "media" && <MediaComposer onClose={() => setStep("closed")} />}
    </>
  );
}

function ChoiceCard({ title, text, onClick, icon }: { title: string; text: string; onClick: () => void; icon: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} className="flex flex-col items-start rounded-[16px] border border-line p-4 text-left transition-colors hover:border-sage hover:bg-sage-tint/20">
      <span className="grid h-11 w-11 place-items-center rounded-full bg-sage-tint/60 text-sage-deep">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          {icon}
        </svg>
      </span>
      <span className="mt-3 text-[16px] font-semibold text-ink">{title}</span>
      <span className="mt-1 text-[14px] text-muted">{text}</span>
    </button>
  );
}

function videoDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => {
      resolve(v.duration);
      URL.revokeObjectURL(v.src);
    };
    v.onerror = () => resolve(0); // not readable here (e.g. HEVC on Windows): the server checks it
    v.src = URL.createObjectURL(file);
  });
}

/** Upload my own photo or video: preview, caption, rules, and a progress bar. */
function MediaComposer({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [agree, setAgree] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<CommunityPost | null>(null);
  const isVideo = !!file && (file.type.startsWith("video/") || /\.(mp4|mov|webm|m4v)$/i.test(file.name));

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const pick = async (f: File | undefined) => {
    setError(null);
    if (!f) return;
    const video = f.type.startsWith("video/") || /\.(mp4|mov|webm|m4v)$/i.test(f.name);
    if (!video && !f.type.startsWith("image/") && !/\.(heic|heif)$/i.test(f.name)) {
      setError("Please choose a photo or a video.");
      return;
    }
    if (video) {
      if (f.size > MAX_VIDEO_MB * 1024 * 1024) {
        setError(`That video is too big. Please use one under ${MAX_VIDEO_MB} MB.`);
        return;
      }
      const seconds = await videoDuration(f);
      if (seconds > MAX_VIDEO_SECONDS + 1) {
        setError(`Videos can be up to ${MAX_VIDEO_SECONDS} seconds; this one is ${Math.round(seconds)}. Please trim it first.`);
        return;
      }
    } else if (f.size > MAX_PHOTO_MB * 1024 * 1024) {
      setError(`That photo is too big. Please use one under ${MAX_PHOTO_MB} MB.`);
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const post = async () => {
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      const created = await community.createMedia(file, caption.trim(), setProgress);
      setDone(created);
      qc.invalidateQueries({ queryKey: ["community"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Upload failed. Please try again.");
    } finally {
      setProgress(null);
    }
  };

  if (done) {
    return (
      <Modal title="Posted" onClose={onClose}>
        <div className="py-6 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-sage text-[26px] text-white">✓</div>
          <p className="mt-4 text-[18px] font-semibold text-ink">Your {done.media_kind === "video" ? "video" : "photo"} is in the community</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Link href={`/community/post/${done.id}`} onClick={onClose} className="inline-flex min-h-[44px] items-center rounded-full bg-sage px-5 text-[15px] font-semibold text-white">
              View my post
            </Link>
            <Link href="/community/reels" onClick={onClose} className="inline-flex min-h-[44px] items-center rounded-full border border-line-strong px-5 text-[15px] font-semibold text-ink">
              Watch Reels
            </Link>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Upload a photo or video" onClose={progress === null ? onClose : () => undefined}>
      {!file ? (
        <label className="flex cursor-pointer flex-col items-center justify-center rounded-[16px] border-2 border-dashed border-line-strong px-6 py-12 text-center hover:border-sage">
          <input type="file" accept="image/*,video/*" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
          <span className="grid h-14 w-14 place-items-center rounded-full bg-sage-tint/60 text-sage-deep">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
            </svg>
          </span>
          <span className="mt-3 text-[16.5px] font-semibold text-ink">Choose a photo or video</span>
          <span className="mt-1 text-[14px] text-muted">
            Photos up to {MAX_PHOTO_MB} MB · videos up to {MAX_VIDEO_SECONDS} seconds and {MAX_VIDEO_MB} MB
          </span>
        </label>
      ) : (
        <>
          <div className="flex gap-4">
            <div className="h-48 w-36 shrink-0 overflow-hidden rounded-xl bg-black">
              {preview &&
                (isVideo ? (
                  <video src={preview} className="h-full w-full object-cover" muted playsInline autoPlay loop />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={preview} alt="" className="h-full w-full object-cover" />
                ))}
            </div>
            <div className="flex min-w-0 flex-1 flex-col">
              <textarea
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                maxLength={1000}
                rows={5}
                placeholder="Write a caption… (optional)"
                aria-label="Caption"
                className="min-h-0 flex-1 rounded-xl border border-line-strong bg-paper p-3 text-[15px] text-ink"
              />
              <button type="button" disabled={progress !== null} onClick={() => setFile(null)} className="mt-2 self-start text-[14px] font-semibold text-sage-deep hover:underline">
                Choose another file
              </button>
            </div>
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
            I agree to the community rules, and I have the right to post this.
          </label>
          {progress !== null && (
            <div className="mt-4" aria-live="polite">
              <div className="h-2 overflow-hidden rounded-full bg-paper-2">
                <div className="h-full rounded-full bg-sage transition-[width]" style={{ width: `${progress}%` }} />
              </div>
              <p className="mt-1.5 text-[13.5px] text-muted">
                {progress < 100 ? `Uploading… ${progress}%` : isVideo ? "Preparing your video… this can take a moment." : "Almost done…"}
              </p>
            </div>
          )}
        </>
      )}
      {error && <p role="alert" className="mt-3 text-[14px] text-[#a4553f]">{error}</p>}
      {file && (
        <div className="mt-5 flex gap-3">
          <button type="button" disabled={progress !== null} onClick={onClose} className="min-h-[46px] flex-1 rounded-full border border-line-strong text-[15px] font-semibold text-ink">
            Cancel
          </button>
          <button
            type="button"
            disabled={!agree || progress !== null}
            onClick={post}
            className="tu-press min-h-[46px] flex-1 rounded-full bg-sage text-[15px] font-semibold text-white disabled:opacity-50"
          >
            {progress !== null ? "Posting…" : "Post"}
          </button>
        </div>
      )}
    </Modal>
  );
}
