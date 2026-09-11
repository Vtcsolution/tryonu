"use client";

import { useEffect, useRef, useState } from "react";

type Stage = { label: string; note: string; accent?: boolean };

const STAGES: Stage[] = [
  { label: "Upload", note: "signed URL" },
  { label: "Validate", note: "type · size" },
  { label: "Optimize", note: "resize · strip EXIF" },
  { label: "Queue", note: "credits reserved" },
  { label: "AI worker", note: "try-on render", accent: true },
  { label: "Store", note: "private object storage" },
  { label: "CDN", note: "signed delivery" },
  { label: "You", note: "compare & shop" },
];

/**
 * "Behind the scenes" strip — the job pipeline lights up stage by stage
 * when it scrolls into view, echoing the real queued → processing →
 * completed lifecycle.
 */
export function Pipeline() {
  const ref = useRef<HTMLDivElement | null>(null);
  const [run, setRun] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setRun(true);
          io.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className="flex flex-wrap items-stretch gap-x-2 gap-y-3 sm:flex-nowrap"
    >
      {STAGES.map((s, i) => (
        <div key={s.label} className="flex min-w-0 flex-1 items-center gap-2">
          <div
            className="min-w-0 flex-1 transform-gpu rounded-2xl border px-3 py-3 text-center transition-[opacity,transform,border-color] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
            style={{
              transitionDelay: `${i * 160}ms`,
              opacity: run ? 1 : 0.25,
              transform: run ? "translateY(0)" : "translateY(8px)",
              borderColor: run
                ? s.accent
                  ? "var(--color-sage)"
                  : "var(--color-line-strong)"
                : "var(--color-line)",
              background: s.accent
                ? "var(--color-sage-tint)"
                : "var(--color-surface)",
            }}
          >
            <span
              className={`block text-[12.5px] font-semibold ${
                s.accent ? "text-sage-deep" : "text-ink"
              }`}
            >
              {s.label}
            </span>
            <span className="mt-0.5 block truncate text-[10.5px] text-muted">
              {s.note}
            </span>
          </div>

          {i < STAGES.length - 1 && (
            <div
              className="hidden h-0.5 w-5 shrink-0 rounded transition-opacity duration-500 sm:block"
              style={{
                transitionDelay: `${i * 160 + 80}ms`,
                opacity: run ? 1 : 0,
                background: "var(--color-sage)",
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
