"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { tryon as tryonApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

/** Share a finished look as a public link (only when its owner presses Share), or stop sharing it. */
export function ShareLook({ jobId }: { jobId: string }) {
  const [open, setOpen] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  const share = useMutation({
    mutationFn: () => tryonApi.share(jobId),
    onSuccess: (res) => {
      setLink(res.url);
      setStopped(false);
    },
  });
  const stop = useMutation({
    mutationFn: () => tryonApi.stopSharing(jobId),
    onSuccess: () => {
      setLink(null);
      setStopped(true);
      setConfirmStop(false);
    },
  });

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const start = () => {
    setOpen(true);
    if (!link && !share.isPending) share.mutate();
  };
  const text = "Here's my look, made with TryOnU";
  const encoded = link ? encodeURIComponent(link) : "";
  const channels = link
    ? [
        { name: "WhatsApp", href: `https://wa.me/?text=${encodeURIComponent(`${text}: ${link}`)}` },
        { name: "Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${encoded}` },
        { name: "X", href: `https://twitter.com/intent/tweet?url=${encoded}&text=${encodeURIComponent(text)}` },
      ]
    : [];
  const canNativeShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  return (
    <div ref={box} className="relative ml-auto">
      <button
        type="button"
        onClick={start}
        aria-expanded={open}
        className="tu-press inline-flex min-h-[42px] items-center gap-2 rounded-full bg-sage px-5 text-[15px] font-semibold text-white hover:bg-sage-deep"
      >
        <span aria-hidden="true">↗</span> Share
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Share this look"
          className="absolute right-0 top-full z-50 mt-2 w-[min(380px,calc(100vw-32px))] rounded-[20px] border border-line bg-surface p-4 shadow-lift"
        >
          <p className="text-[16px] font-semibold text-ink">Share your look</p>
          <p className="mt-1 text-[13.5px] text-muted">
            Anyone with the link sees this picture and the products in it. You can stop sharing any time.
          </p>
          {share.isPending && <p className="mt-3 text-[14px] text-muted">Making your link…</p>}
          {share.isError && (
            <p role="alert" className="mt-3 text-[14px] text-[#a4553f]">
              {share.error instanceof ApiError ? share.error.detail : "Couldn't make the link. Please try again."}
            </p>
          )}
          {stopped && !link && (
            <p className="mt-3 rounded-xl bg-paper-2 px-3 py-2 text-[14px] text-ink">
              Sharing stopped: the link no longer works.{" "}
              <button type="button" onClick={() => share.mutate()} className="font-medium text-sage-deep hover:underline">
                Share again
              </button>
            </p>
          )}
          {link && (
            <>
              <div className="mt-3 flex items-center gap-2">
                <input
                  readOnly
                  value={link}
                  onFocus={(e) => e.currentTarget.select()}
                  className="h-10 min-w-0 flex-1 rounded-xl border border-line-strong bg-paper-2 px-3 text-[13.5px] text-ink"
                  aria-label="Link to your look"
                />
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(link);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 1800);
                    } catch {
                      setCopied(false);
                    }
                  }}
                  className="tu-press min-h-[40px] shrink-0 rounded-full bg-ink px-4 text-[14px] font-semibold text-surface"
                >
                  {copied ? "✓ Copied" : "Copy"}
                </button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {canNativeShare && (
                  <button
                    type="button"
                    onClick={() => navigator.share({ title: "My TryOnU look", text, url: link }).catch(() => undefined)}
                    className="tu-press min-h-[40px] rounded-full border border-line-strong px-4 text-[14px] font-medium text-ink hover:border-ink/40"
                  >
                    Share…
                  </button>
                )}
                {channels.map((c) => (
                  <a
                    key={c.name}
                    href={c.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="tu-press inline-flex min-h-[40px] items-center rounded-full border border-line-strong px-4 text-[14px] font-medium text-ink hover:border-ink/40"
                  >
                    {c.name}
                  </a>
                ))}
                <a
                  href={link}
                  target="_blank"
                  rel="noopener"
                  className="tu-press inline-flex min-h-[40px] items-center rounded-full border border-line-strong px-4 text-[14px] font-medium text-ink hover:border-ink/40"
                >
                  Open ↗
                </a>
              </div>
              <div className="mt-3 border-t border-line pt-3">
                {confirmStop ? (
                  <span className="flex flex-wrap items-center gap-2 text-[13.5px] text-ink-soft">
                    Stop sharing? The link stops working.
                    <button
                      type="button"
                      disabled={stop.isPending}
                      onClick={() => stop.mutate()}
                      className="font-semibold text-[#a4553f] hover:underline"
                    >
                      Yes, stop
                    </button>
                    <button type="button" onClick={() => setConfirmStop(false)} className="text-muted hover:text-ink">
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button type="button" onClick={() => setConfirmStop(true)} className="text-[13.5px] text-muted hover:text-[#a4553f]">
                    Stop sharing
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
