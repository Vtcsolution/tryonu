"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { tryon as tryonApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

type Props = {
  /** the owner's finished look: makes (or reuses) its public link, and can stop sharing */
  jobId?: string;
  /** an already public link (a visitor passing a shared look on) */
  url?: string;
  /** "pill": small button beside a title; "wide": full-width button in a list of actions */
  variant?: "pill" | "wide";
};

const TEXT = "Here's my look, made with TryOnU";

/** Share a look: a pop-up with Facebook, LinkedIn, X, WhatsApp and Copy link. */
export function ShareLook({ jobId, url, variant = "pill" }: Props) {
  const [open, setOpen] = useState(false);
  const [link, setLink] = useState<string | null>(url ?? null);
  const [copied, setCopied] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);

  const share = useMutation({
    mutationFn: () => tryonApi.share(jobId!),
    onSuccess: (res) => {
      setLink(res.url);
      setStopped(false);
    },
  });
  const stop = useMutation({
    mutationFn: () => tryonApi.stopSharing(jobId!),
    onSuccess: () => {
      setLink(null);
      setStopped(true);
      setConfirmStop(false);
    },
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [open]);

  const start = () => {
    setOpen(true);
    setCopied(false);
    if (!link && jobId && !share.isPending) share.mutate();
  };
  const copy = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
    } catch {
      // older browsers: select the box so the shopper can copy it themselves
      (document.getElementById("tu-share-link") as HTMLInputElement | null)?.select();
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const encoded = link ? encodeURIComponent(link) : "";
  const channels: { name: string; color: string; href: string; icon: ReactNode }[] = link
    ? [
        { name: "Facebook", color: "#3b5998", href: `https://www.facebook.com/sharer/sharer.php?u=${encoded}`, icon: <FacebookIcon /> },
        { name: "LinkedIn", color: "#0a66c2", href: `https://www.linkedin.com/sharing/share-offsite/?url=${encoded}`, icon: <LinkedInIcon /> },
        { name: "X", color: "#111111", href: `https://twitter.com/intent/tweet?url=${encoded}&text=${encodeURIComponent(TEXT)}`, icon: <XIcon /> },
        { name: "WhatsApp", color: "#25d366", href: `https://wa.me/?text=${encodeURIComponent(`${TEXT}: ${link}`)}`, icon: <WhatsAppIcon /> },
      ]
    : [];
  const canNativeShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  const trigger =
    variant === "wide" ? (
      <button
        type="button"
        onClick={start}
        className="tu-press flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full border border-sage bg-sage-tint/40 px-5 text-[16px] font-semibold text-ink hover:bg-sage-tint/70"
      >
        <ShareIcon /> Share this look
      </button>
    ) : (
      <button
        type="button"
        onClick={start}
        className="tu-press ml-auto inline-flex min-h-[44px] items-center gap-2 rounded-full bg-sage px-5 text-[15px] font-semibold text-white hover:bg-sage-deep"
      >
        <ShareIcon /> Share
      </button>
    );

  const dialog = open ? (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Share this look"
        className="relative w-full max-w-[560px] rounded-[24px] bg-surface px-6 pb-6 pt-8 text-center shadow-lift sm:px-10"
      >
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Close"
          className="absolute right-3 top-3 grid h-10 w-10 place-items-center rounded-full text-[24px] text-muted hover:bg-paper-2 hover:text-ink"
        >
          ×
        </button>
        <h2 className="font-display text-[28px] text-ink">Share your look</h2>
        <p className="mx-auto mt-1 max-w-[400px] text-[15px] text-ink-soft">
          Anyone with the link sees this picture and the products in it, and can try them on too.
        </p>

        {share.isPending && <p className="mt-6 text-[15px] text-muted">Making your link…</p>}
        {share.isError && (
          <p role="alert" className="mt-6 text-[15px] text-[#a4553f]">
            {share.error instanceof ApiError ? share.error.detail : "Couldn't make the link. Please try again."}{" "}
            <button type="button" onClick={() => share.mutate()} className="font-semibold underline">
              Try again
            </button>
          </p>
        )}
        {stopped && !link && (
          <p className="mt-6 rounded-xl bg-paper-2 px-3 py-3 text-[15px] text-ink">
            Sharing stopped: the link no longer works.{" "}
            <button type="button" onClick={() => share.mutate()} className="font-semibold text-sage-deep hover:underline">
              Share again
            </button>
          </p>
        )}

        {link && (
          <>
            <div className="mt-7 flex flex-wrap justify-center gap-x-5 gap-y-4">
              {channels.map((c) => (
                <a
                  key={c.name}
                  href={c.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex w-[76px] flex-col items-center gap-2 text-[14px] text-ink"
                >
                  <span
                    className="grid h-[62px] w-[62px] place-items-center rounded-full text-white transition-transform group-hover:scale-105"
                    style={{ background: c.color }}
                  >
                    {c.icon}
                  </span>
                  {c.name}
                </a>
              ))}
              <button type="button" onClick={copy} className="group flex w-[76px] flex-col items-center gap-2 text-[14px] text-ink">
                <span
                  className={`grid h-[62px] w-[62px] place-items-center rounded-full border transition-transform group-hover:scale-105 ${
                    copied ? "border-sage bg-sage text-white" : "border-line-strong bg-surface text-ink-soft"
                  }`}
                >
                  {copied ? <span className="text-[24px]">✓</span> : <LinkIcon />}
                </span>
                {copied ? "Copied!" : "Copy link"}
              </button>
            </div>

            <div className="mt-6 flex items-center gap-2">
              <input
                id="tu-share-link"
                readOnly
                value={link}
                onFocus={(e) => e.currentTarget.select()}
                className="h-11 min-w-0 flex-1 rounded-xl border border-line-strong bg-paper-2 px-3 text-[14px] text-ink"
                aria-label="Link to the look"
              />
              <button
                type="button"
                onClick={copy}
                className="tu-press min-h-[44px] shrink-0 rounded-full bg-ink px-5 text-[14.5px] font-semibold text-surface"
              >
                {copied ? "✓ Copied" : "Copy"}
              </button>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-[14px]">
              {canNativeShare && (
                <button
                  type="button"
                  onClick={() => navigator.share({ title: "My TryOnU look", text: TEXT, url: link }).catch(() => undefined)}
                  className="font-medium text-sage-deep hover:underline"
                >
                  More apps…
                </button>
              )}
              <a href={link} target="_blank" rel="noopener" className="font-medium text-sage-deep hover:underline">
                Preview the page ↗
              </a>
            </div>

            {jobId && (
              <div className="mt-5 border-t border-line pt-4 text-[14px]">
                {confirmStop ? (
                  <span className="flex flex-wrap items-center justify-center gap-3 text-ink-soft">
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
                  <button type="button" onClick={() => setConfirmStop(true)} className="text-muted hover:text-[#a4553f]">
                    Stop sharing this look
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  ) : null;

  return (
    <>
      {trigger}
      {dialog && typeof document !== "undefined" ? createPortal(dialog, document.body) : null}
    </>
  );
}

function ShareIcon() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg aria-hidden="true" width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
      <path d="M13.5 21v-7.5h2.6l.4-3h-3V8.6c0-.9.3-1.5 1.5-1.5h1.6V4.4c-.3 0-1.2-.1-2.3-.1-2.3 0-3.8 1.4-3.8 3.9v2.3H8v3h2.5V21h3z" />
    </svg>
  );
}

function LinkedInIcon() {
  return (
    <svg aria-hidden="true" width="26" height="26" viewBox="0 0 24 24" fill="currentColor">
      <rect x="3.5" y="9" width="3.6" height="11" rx=".4" />
      <circle cx="5.3" cy="5.3" r="2.1" />
      <path d="M9.6 9h3.4v1.6c.6-1 1.8-1.9 3.6-1.9 3 0 3.9 1.9 3.9 4.8V20h-3.6v-5.8c0-1.4-.3-2.6-1.8-2.6s-2 1.1-2 2.6V20H9.6V9z" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M4 3.5h4.6l4 5.6 4.8-5.6h2.2l-6 7 6.9 10h-4.6l-4.4-6.2-5.3 6.2H4l6.6-7.6L4 3.5zm3 1.6 9.6 13.8h1.4L8.4 5.1H7z" />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg aria-hidden="true" width="30" height="30" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3.2a8.8 8.8 0 0 0-7.6 13.2L3.2 20.8l4.5-1.2A8.8 8.8 0 1 0 12 3.2z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M9.2 7.6c-.3 0-.7.1-1 .5-.3.4-1 1-1 2.4s1 2.8 1.2 3c.2.2 2 3.1 4.9 4.2 2.4.9 2.9.8 3.4.7.5-.1 1.7-.7 1.9-1.4.2-.7.2-1.3.2-1.4-.1-.1-.3-.2-.6-.4l-1.9-.9c-.3-.1-.5-.1-.7.1l-.9 1.1c-.2.2-.3.2-.6.1-.3-.2-1.2-.5-2.3-1.4-.9-.8-1.4-1.7-1.6-2-.2-.3 0-.5.1-.6l.5-.6c.2-.2.2-.3.3-.5.1-.2 0-.4 0-.5l-.9-2.1c-.2-.5-.4-.5-.6-.5h-.5z"
        fill="currentColor"
      />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg aria-hidden="true" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13.5a4.5 4.5 0 0 0 6.4.4l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2" />
      <path d="M14 10.5a4.5 4.5 0 0 0-6.4-.4l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2" />
    </svg>
  );
}
