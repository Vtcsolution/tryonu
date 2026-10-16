"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { referrals as referralsApi, tryon as tryonApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import { ApiError } from "@/lib/api/client";

type Props = {
  /** the owner's finished look: makes (or reuses) its public link, and can stop sharing */
  jobId?: string;
  /** an already public link (a visitor passing a shared look on) */
  url?: string;
  /** "pill": small button beside a title; "wide": full-width button in a list of actions */
  variant?: "pill" | "wide";
  /** the button's words (default: "Share" / "Share this look") */
  label?: string;
  /** the pop-up's heading, and the message sent with the link */
  title?: string;
  message?: string;
  /** the link earns the signed-in person credits (their own look, or their invite link) */
  earns?: boolean;
};

const LOOK_TEXT = "Here's my look, made with TryOnU. Try it on yourself:";

/** Share a look (or an invite link): copy the link, or send it to Facebook,
 * LinkedIn, X, WhatsApp or email. */
export function ShareLook({ jobId, url, variant = "pill", label, title = "Share this look", message = LOOK_TEXT, earns }: Props) {
  const { user } = useSession();
  const earn = useQuery({ queryKey: ["referrals", "me"], queryFn: referralsApi.me, enabled: !!user, staleTime: 5 * 60_000 });
  const reward = earn.data?.reward_credits ?? 0;
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
    setConfirmStop(false);
    if (!link && jobId && !share.isPending) share.mutate();
  };
  const copy = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
    } catch {
      // older browsers: select the box so it can be copied by hand
      (document.getElementById("tu-share-link") as HTMLInputElement | null)?.select();
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const encoded = link ? encodeURIComponent(link) : "";
  const channels: { name: string; href: string; icon: ReactNode }[] = link
    ? [
        { name: "WhatsApp", href: `https://wa.me/?text=${encodeURIComponent(`${message} ${link}`)}`, icon: <WhatsAppIcon /> },
        { name: "Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${encoded}`, icon: <FacebookIcon /> },
        { name: "LinkedIn", href: `https://www.linkedin.com/sharing/share-offsite/?url=${encoded}`, icon: <LinkedInIcon /> },
        { name: "X", href: `https://twitter.com/intent/tweet?url=${encoded}&text=${encodeURIComponent(message)}`, icon: <XIcon /> },
        {
          name: "Email",
          href: `mailto:?subject=${encodeURIComponent(jobId || !earns ? "A look on TryOnU" : "Join me on TryOnU")}&body=${encodeURIComponent(`${message}\n${link}`)}`,
          icon: <MailIcon />,
        },
      ]
    : [];
  const canNativeShare = typeof navigator !== "undefined" && typeof navigator.share === "function";
  const showReward = reward > 0 && (earns ?? !!jobId);

  const trigger =
    variant === "wide" ? (
      <button
        type="button"
        onClick={start}
        className="tu-press flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full border border-line-strong bg-surface px-5 text-[15.5px] font-semibold text-ink hover:border-ink/40"
      >
        <ShareIcon /> {label ?? "Share this look"}
      </button>
    ) : (
      <button
        type="button"
        onClick={start}
        className="tu-press ml-auto inline-flex min-h-[44px] items-center gap-2 rounded-full bg-sage px-5 text-[15px] font-semibold text-white hover:bg-sage-deep"
      >
        <ShareIcon /> {label ?? "Share"}
      </button>
    );

  const sectionLabel = "text-[12.5px] font-semibold uppercase tracking-[0.08em] text-faint";

  const dialog = open ? (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tu-share-title"
        className="relative w-full max-w-[500px] rounded-t-[20px] border border-line bg-surface p-5 text-left shadow-lift sm:rounded-[20px] sm:p-6"
      >
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 id="tu-share-title" className="text-[19px] font-semibold text-ink">{title}</h2>
            <p className="mt-1 text-[14.5px] leading-relaxed text-muted">
              {jobId
                ? "Anyone with the link can see this picture and its products, and try them on themselves."
                : "Send this link to friends, or post it on social media."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close"
            className="-mr-1 -mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-paper-2 hover:text-ink"
          >
            <CloseIcon />
          </button>
        </div>

        {share.isPending && <p className="mt-5 text-[14.5px] text-muted">Creating your link…</p>}
        {share.isError && (
          <p role="alert" className="mt-5 text-[14.5px] text-[#a4553f]">
            {share.error instanceof ApiError ? share.error.detail : "The link couldn't be created."}{" "}
            <button type="button" onClick={() => share.mutate()} className="font-semibold underline">
              Try again
            </button>
          </p>
        )}
        {stopped && !link && (
          <div className="mt-5 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line px-4 py-3 text-[14.5px] text-ink-soft">
            Sharing is off. The old link no longer works.
            <button type="button" onClick={() => share.mutate()} className="font-semibold text-sage-deep hover:underline">
              Share again
            </button>
          </div>
        )}

        {link && (
          <>
            <p className={`mt-5 ${sectionLabel}`}>Link</p>
            <div className="mt-2 flex items-center gap-2">
              <input
                id="tu-share-link"
                readOnly
                value={link}
                onFocus={(e) => e.currentTarget.select()}
                className="h-11 min-w-0 flex-1 rounded-xl border border-line-strong bg-paper-2 px-3 font-mono text-[13px] text-ink-soft"
                aria-label="Share link"
              />
              <button
                type="button"
                onClick={copy}
                className={`tu-press inline-flex h-11 shrink-0 items-center gap-1.5 rounded-xl px-4 text-[14.5px] font-semibold ${
                  copied ? "bg-sage text-white" : "bg-ink text-surface hover:bg-ink/90"
                }`}
              >
                {copied ? <CheckIcon /> : <LinkIcon />}
                {copied ? "Copied" : "Copy link"}
              </button>
            </div>

            <p className={`mt-5 ${sectionLabel}`}>Share to</p>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {channels.map((c) => (
                <a
                  key={c.name}
                  href={c.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-11 items-center gap-2.5 rounded-xl border border-line px-3 text-[14.5px] font-medium text-ink transition-colors hover:border-line-strong hover:bg-paper-2"
                >
                  {c.icon}
                  {c.name}
                </a>
              ))}
              {canNativeShare && (
                <button
                  type="button"
                  onClick={() => navigator.share({ title: "TryOnU", text: message, url: link }).catch(() => undefined)}
                  className="flex h-11 items-center gap-2.5 rounded-xl border border-line px-3 text-[14.5px] font-medium text-ink transition-colors hover:border-line-strong hover:bg-paper-2"
                >
                  <MoreIcon />
                  More apps
                </button>
              )}
            </div>

            {showReward && (
              <div className="mt-5 flex items-start gap-3 rounded-xl border border-sage/30 bg-sage-tint/20 px-4 py-3">
                <span className="mt-0.5 text-sage-deep">
                  <GiftIcon />
                </span>
                <p className="text-[14px] leading-relaxed text-ink-soft">
                  You earn <span className="font-semibold text-ink">{reward} credits</span> for each friend who signs up through
                  this link and makes their first purchase.
                </p>
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-[14px]">
              <a href={link} target="_blank" rel="noopener" className="inline-flex items-center gap-1 font-medium text-ink-soft hover:text-ink">
                Preview page <ExternalIcon />
              </a>
              {jobId &&
                (confirmStop ? (
                  <span className="inline-flex flex-wrap items-center gap-3 text-ink-soft">
                    The link will stop working.
                    <button
                      type="button"
                      disabled={stop.isPending}
                      onClick={() => stop.mutate()}
                      className="font-semibold text-[#a4553f] hover:underline"
                    >
                      Stop sharing
                    </button>
                    <button type="button" onClick={() => setConfirmStop(false)} className="text-muted hover:text-ink">
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button type="button" onClick={() => setConfirmStop(true)} className="text-muted hover:text-[#a4553f]">
                    Stop sharing
                  </button>
                ))}
            </div>
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

/* ------------------------------------------------------------------ icons (18px, brand colour only on the mark) */

const svg = { width: 18, height: 18, viewBox: "0 0 24 24", "aria-hidden": true } as const;
const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function ShareIcon() {
  return (
    <svg {...svg} {...stroke}>
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg {...svg}>
      <circle cx="12" cy="12" r="10" fill="#1877f2" />
      <path
        fill="#fff"
        d="M13.4 21.9v-7.1h2.3l.4-2.8h-2.7v-1.8c0-.8.3-1.4 1.4-1.4h1.4V6.3c-.3 0-1.1-.1-2.1-.1-2.1 0-3.5 1.3-3.5 3.6V12H8.3v2.8h2.3v7.1h2.8z"
      />
    </svg>
  );
}

function LinkedInIcon() {
  return (
    <svg {...svg}>
      <rect x="2" y="2" width="20" height="20" rx="3" fill="#0a66c2" />
      <rect x="5.6" y="9.5" width="2.8" height="8.5" fill="#fff" />
      <circle cx="7" cy="6.6" r="1.6" fill="#fff" />
      <path fill="#fff" d="M10.6 9.5h2.7v1.2c.4-.7 1.4-1.4 2.8-1.4 2.4 0 3 1.5 3 3.7V18h-2.8v-4.5c0-1.1-.2-2-1.4-2s-1.5.9-1.5 2V18h-2.8V9.5z" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg {...svg} fill="currentColor">
      <path d="M4 3.5h4.6l4 5.6 4.8-5.6h2.2l-6 7 6.9 10h-4.6l-4.4-6.2-5.3 6.2H4l6.6-7.6L4 3.5zm3 1.6 9.6 13.8h1.4L8.4 5.1H7z" />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg {...svg}>
      <path fill="#25d366" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2z" />
      <path
        fill="#fff"
        d="M9.1 7.2c-.2 0-.6.1-.9.4-.3.3-1.1 1.1-1.1 2.6s1.1 3 1.3 3.2c.2.2 2.2 3.4 5.3 4.6 2.6 1 3.1.8 3.7.8.6-.1 1.8-.7 2-1.5.3-.7.3-1.4.2-1.5-.1-.1-.3-.2-.6-.4l-2-1c-.3-.1-.5-.1-.7.1l-1 1.2c-.2.2-.4.3-.7.1-.3-.2-1.3-.5-2.5-1.5-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.6l.5-.6c.2-.2.2-.3.3-.5.1-.2.1-.4 0-.6l-.9-2.2c-.2-.5-.5-.5-.7-.5h-.6z"
      />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg {...svg} {...stroke}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </svg>
  );
}

function MoreIcon() {
  return (
    <svg {...svg} fill="currentColor">
      <circle cx="5" cy="12" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <circle cx="19" cy="12" r="1.8" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" aria-hidden {...stroke}>
      <path d="M10 13.5a4.5 4.5 0 0 0 6.4.4l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2" />
      <path d="M14 10.5a4.5 4.5 0 0 0-6.4-.4l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" aria-hidden {...stroke} strokeWidth={2.6}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg {...svg} {...stroke}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

function ExternalIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" aria-hidden {...stroke}>
      <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </svg>
  );
}

function GiftIcon() {
  return (
    <svg {...svg} {...stroke}>
      <rect x="3.5" y="8" width="17" height="4" rx="1" />
      <path d="M5 12v8h14v-8M12 8v12M12 8c-1.5-3-5-3.5-5-1.3C7 8 9 8 12 8zm0 0c1.5-3 5-3.5 5-1.3C17 8 15 8 12 8z" />
    </svg>
  );
}
