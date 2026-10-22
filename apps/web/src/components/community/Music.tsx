"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { resolveMediaUrl } from "@/lib/api/client";
import { community, type MusicTrack } from "@/lib/api/endpoints";

export const MOODS: { id: string; label: string }[] = [
  { id: "happy", label: "Happy" },
  { id: "chill", label: "Chill" },
  { id: "party", label: "Party" },
  { id: "romantic", label: "Romantic" },
  { id: "desi", label: "Desi" },
  { id: "classic", label: "Classic" },
];

export function MusicNote({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  );
}

function PlayIcon({ playing }: { playing: boolean }) {
  return playing ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <rect x="6" y="5" width="4" height="14" rx="1" />
      <rect x="14" y="5" width="4" height="14" rx="1" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

export const songName = (t: Pick<MusicTrack, "title" | "artist">) => (t.artist ? `${t.title} · ${t.artist}` : t.title);

/** "Add music" on a new post: the free library, a tap to listen, a tap to choose. Hidden while the library is empty. */
export function MusicPicker({ value, onChange }: { value: string | null | undefined; onChange: (id: string | null) => void }) {
  const library = useQuery({ queryKey: ["community", "music"], queryFn: community.music, staleTime: 5 * 60_000 });
  const [open, setOpen] = useState(false);
  const [mood, setMood] = useState<string | null>(null);
  const [listening, setListening] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);

  useEffect(() => () => audio.current?.pause(), []);
  const tracks = library.data ?? [];
  if (tracks.length === 0) return null;
  const chosen = tracks.find((t) => t.id === value) ?? null;
  const moods = MOODS.filter((m) => tracks.some((t) => t.mood === m.id));
  const shown = mood ? tracks.filter((t) => t.mood === mood) : tracks;

  const listen = (t: MusicTrack) => {
    if (!audio.current) audio.current = new Audio();
    const a = audio.current;
    if (listening === t.id) {
      a.pause();
      setListening(null);
      return;
    }
    a.src = resolveMediaUrl(t.url);
    a.currentTime = 0;
    a.play().catch(() => undefined);
    a.onended = () => setListening(null);
    setListening(t.id);
  };
  const close = () => {
    audio.current?.pause();
    setListening(null);
    setOpen(false);
  };

  return (
    <div className="rounded-xl border border-line p-3">
      {chosen ? (
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-sage text-white">
            <MusicNote />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] text-muted">Music</span>
            <span className="block truncate text-[15px] font-semibold text-ink">{songName(chosen)}</span>
          </span>
          <button type="button" onClick={() => setOpen(true)} className="tu-tap min-h-[40px] rounded-full border border-line-strong px-3 text-[14px] font-semibold text-ink">
            Change
          </button>
          <button type="button" onClick={() => onChange(null)} aria-label="Remove the music" className="tu-tap grid h-10 w-10 place-items-center rounded-full text-[20px] text-muted hover:bg-paper-2">
            ×
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setOpen(true)} className="tu-tap flex w-full items-center gap-3 text-left">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-paper-2 text-ink">
            <MusicNote />
          </span>
          <span>
            <span className="block text-[15px] font-semibold text-ink">Add music</span>
            <span className="block text-[13.5px] text-muted">Free songs. They play with your post in Reels.</span>
          </span>
        </button>
      )}

      {open && (
        <div className="mt-3 border-t border-line pt-3">
          {moods.length > 1 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {[{ id: null as string | null, label: "All" }, ...moods].map((m) => (
                <button
                  key={m.label}
                  type="button"
                  onClick={() => setMood(m.id)}
                  className={`min-h-[34px] rounded-full px-3 text-[13.5px] font-semibold ${mood === m.id ? "bg-ink text-paper" : "border border-line text-ink-soft"}`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          )}
          <ul className="max-h-[260px] space-y-1 overflow-y-auto">
            {shown.map((t) => (
              <li key={t.id} className={`flex items-center gap-2 rounded-xl p-1.5 ${t.id === value ? "bg-sage/10" : ""}`}>
                <button
                  type="button"
                  onClick={() => listen(t)}
                  aria-label={listening === t.id ? `Stop ${t.title}` : `Listen to ${t.title}`}
                  className="tu-tap grid h-10 w-10 shrink-0 place-items-center rounded-full bg-paper-2 text-ink"
                >
                  <PlayIcon playing={listening === t.id} />
                </button>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] text-ink">{t.title}</span>
                  {t.artist && <span className="block truncate text-[12.5px] text-muted">{t.artist}</span>}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    onChange(t.id);
                    close();
                  }}
                  className="tu-press min-h-[36px] shrink-0 rounded-full bg-sage px-3.5 text-[13.5px] font-semibold text-white"
                >
                  {t.id === value ? "Chosen" : "Use"}
                </button>
              </li>
            ))}
          </ul>
          <button type="button" onClick={close} className="mt-2 w-full min-h-[40px] text-[14px] font-semibold text-muted">
            Close
          </button>
        </div>
      )}
    </div>
  );
}

/** "♪ Song · Artist", sliding across like TikTok's sound label. */
export function SongLabel({ track, className = "" }: { track: Pick<MusicTrack, "title" | "artist">; className?: string }) {
  const text = songName(track);
  return (
    <span className={`flex min-w-0 items-center gap-1.5 ${className}`}>
      <MusicNote size={15} />
      <span className="min-w-0 flex-1 overflow-hidden">
        <span className="tu-marquee inline-block whitespace-nowrap">
          {text}
          <span className="px-6" aria-hidden="true">
            ·
          </span>
          <span aria-hidden="true">{text}</span>
        </span>
      </span>
    </span>
  );
}
