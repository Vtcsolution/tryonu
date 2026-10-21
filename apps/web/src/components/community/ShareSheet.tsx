"use client";

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { WhatsAppIcon } from "@/components/whatsapp/WhatsApp";

type App = { name: string; color: string; icon: ReactNode; href: (url: string, text: string) => string };

const enc = encodeURIComponent;
const glyph = (t: string, size = 20) => <span style={{ fontSize: size }} className="font-bold leading-none">{t}</span>;

// the famous ones, in the order most people here use them
const APPS: App[] = [
  { name: "WhatsApp", color: "#1fa855", icon: <WhatsAppIcon size={26} />, href: (u, t) => `https://wa.me/?text=${enc(`${t} ${u}`)}` },
  { name: "Facebook", color: "#1877f2", icon: glyph("f", 26), href: (u) => `https://www.facebook.com/sharer/sharer.php?u=${enc(u)}` },
  { name: "Messenger", color: "#0084ff", icon: <MessengerIcon />, href: (u) => `fb-messenger://share/?link=${enc(u)}` },
  { name: "X", color: "#000000", icon: glyph("𝕏", 22), href: (u, t) => `https://twitter.com/intent/tweet?text=${enc(t)}&url=${enc(u)}` },
  { name: "Telegram", color: "#229ed9", icon: <TelegramIcon />, href: (u, t) => `https://t.me/share/url?url=${enc(u)}&text=${enc(t)}` },
  { name: "LinkedIn", color: "#0a66c2", icon: glyph("in", 19), href: (u) => `https://www.linkedin.com/sharing/share-offsite/?url=${enc(u)}` },
  { name: "Pinterest", color: "#e60023", icon: glyph("P", 24), href: (u, t) => `https://pinterest.com/pin/create/button/?url=${enc(u)}&description=${enc(t)}` },
  { name: "Email", color: "#6b7280", icon: <MailIcon />, href: (u, t) => `mailto:?subject=${enc("A look on TryOnU")}&body=${enc(`${t}\n${u}`)}` },
];
// Messenger's app link only opens on phones
const DESKTOP_SKIP = new Set(["Messenger"]);

function usePhone(): boolean {
  const [phone, setPhone] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    const set = () => setPhone(mq.matches);
    set();
    mq.addEventListener("change", set);
    return () => mq.removeEventListener("change", set);
  }, []);
  return phone;
}

/** Share a link: on phones a sheet from the bottom (copy link, the apps, and the phone's own share list);
 *  on computers a box with the link to copy and the famous apps. */
export function ShareSheet({ url, text, title = "Share", note, onClose }: { url: string; text: string; title?: string; note?: string; onClose: () => void }) {
  const phone = usePhone();
  const [copied, setCopied] = useState(false);
  const canNative = typeof navigator !== "undefined" && "share" in navigator;

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("Copy this link", url);
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  const native = () => navigator.share({ title: "TryOnU", text, url }).then(onClose).catch(() => undefined);
  const apps = phone ? APPS : APPS.filter((a) => !DESKTOP_SKIP.has(a.name));

  const grid = (
    <div className={`grid gap-y-4 ${phone ? "grid-cols-4" : "grid-cols-4 sm:grid-cols-7"}`}>
      {apps.map((a) => (
        <a
          key={a.name}
          href={a.href(url, text)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => setTimeout(onClose, 200)}
          className="tu-tap flex flex-col items-center gap-1.5 text-[12.5px] text-ink-soft"
        >
          <span className="grid h-[52px] w-[52px] place-items-center rounded-full text-white" style={{ backgroundColor: a.color }}>
            {a.icon}
          </span>
          {a.name}
        </a>
      ))}
    </div>
  );

  return createPortal(
    <div
      className={`fixed inset-0 z-[90] flex bg-black/50 ${phone ? "items-end" : "items-center justify-center p-4"}`}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={
          phone
            ? "w-full rounded-t-[24px] bg-surface px-4 pb-[calc(16px+env(safe-area-inset-bottom))] pt-2 text-ink"
            : "w-full max-w-[560px] rounded-[22px] bg-surface p-6 text-ink shadow-lift"
        }
      >
        {phone && <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-line-strong" aria-hidden="true" />}
        <div className="flex items-center justify-between">
          <p className="text-[18px] font-semibold">{title}</p>
          <button type="button" onClick={onClose} aria-label="Close" className="grid h-10 w-10 place-items-center rounded-full text-[24px] text-muted hover:bg-paper-2">
            ×
          </button>
        </div>

        {phone ? (
          <>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button type="button" onClick={copy} className="tu-press flex min-h-[52px] items-center justify-center gap-2 rounded-2xl bg-paper-2 text-[15.5px] font-semibold">
                <LinkIcon /> {copied ? "Copied ✓" : "Copy link"}
              </button>
              {canNative ? (
                <button type="button" onClick={native} className="tu-press flex min-h-[52px] items-center justify-center gap-2 rounded-2xl bg-sage text-[15.5px] font-semibold text-white">
                  <MoreIcon /> More apps
                </button>
              ) : (
                <a href={APPS[0].href(url, text)} target="_blank" rel="noopener noreferrer" className="tu-press flex min-h-[52px] items-center justify-center gap-2 rounded-2xl bg-[#1fa855] text-[15.5px] font-semibold text-white">
                  <WhatsAppIcon size={20} /> WhatsApp
                </a>
              )}
            </div>
            <div className="mt-5">{grid}</div>
          </>
        ) : (
          <>
            <div className="mt-4 flex gap-2">
              <input
                readOnly
                value={url}
                onFocus={(e) => e.currentTarget.select()}
                aria-label="Link"
                className="min-w-0 flex-1 rounded-full border border-line bg-paper-2 px-4 py-2.5 text-[14.5px] text-ink-soft"
              />
              <button type="button" onClick={copy} className="tu-press shrink-0 rounded-full bg-sage px-5 text-[15px] font-semibold text-white">
                {copied ? "Copied ✓" : "Copy link"}
              </button>
            </div>
            <div className="mt-6">{grid}</div>
            {canNative && (
              <button type="button" onClick={native} className="mt-5 text-[14.5px] font-semibold text-sage-deep hover:underline">
                More ways to share…
              </button>
            )}
          </>
        )}
        {note && <p className="mt-4 text-[12.5px] text-faint">{note}</p>}
      </div>
    </div>,
    document.body,
  );
}

/** A community post's link and words, for ShareSheet. */
export function postShare(post: { id: string; caption: string | null; author: { handle: string } }) {
  const url = typeof window !== "undefined" ? `${window.location.origin}/community/post/${post.id}` : "";
  const text = post.caption ? `${post.caption} — on TryOnU` : `A look by @${post.author.handle} on TryOnU`;
  return { url, text, title: "Share this post", note: "Friends sign in to TryOnU to see community posts." };
}

export function ShareIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 4l7 7-7 7v-4c-5 0-8.5 1.5-11 5 1-5 4-10 11-11V4z" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" />
    </svg>
  );
}

function MoreIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="5" cy="12" r="2" />
      <circle cx="12" cy="12" r="2" />
      <circle cx="19" cy="12" r="2" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </svg>
  );
}

function TelegramIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M21.5 4.3 2.9 11.5c-1 .4-1 1.5 0 1.8l4.7 1.5 1.8 5.6c.2.7 1.1.9 1.6.4l2.6-2.4 4.9 3.6c.6.4 1.4.1 1.6-.6l3.2-15.3c.2-.9-.7-1.6-1.8-1.8ZM9.9 14.6l-.4 3.9-1.5-4.5 9.6-6.1-7.7 6.7Z" />
    </svg>
  );
}

function MessengerIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.4 2 2 6.1 2 11.6c0 2.9 1.2 5.4 3.2 7.1V22l3-1.7c1.2.3 2.4.5 3.8.5 5.6 0 10-4.1 10-9.6S17.6 2 12 2Zm1 12.9-2.6-2.7-5 2.7 5.5-5.8 2.6 2.7 4.9-2.7-5.4 5.8Z" />
    </svg>
  );
}
