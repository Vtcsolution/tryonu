"use client";

import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";

/**
 * Interactive before/after wipe: one person, before and after a real TryOnU
 * try-on (public/showcase). She is an AI-generated model made for our quality
 * tests, not a real customer, so the label says so. Both pictures are the same
 * size and pose, so the wipe lines up.
 */
const BEFORE = { src: "/showcase/before.jpg", alt: "Before: a woman in a white T-shirt, black trousers and white sneakers" };
const AFTER = {
  src: "/showcase/after.jpg",
  alt: "After a TryOnU try-on: the same woman in a pink embroidered suit with a dupatta, a brown tote bag, a watch and sandals",
};
export function CompareSlider() {
  const [pos, setPos] = useState(50);
  const id = useId();
  // the "original" half is drawn at the frame's full width, then clipped
  const frame = useRef<HTMLDivElement>(null);
  const [frameWidth, setFrameWidth] = useState<number | null>(null);
  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setFrameWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="relative">
      {/* a portrait frame, like the photos: the whole person shows on every screen */}
      <div
        ref={frame}
        className="relative mx-auto aspect-[2/3] w-full max-w-[460px] overflow-hidden rounded-[28px] border border-line bg-paper-2 shadow-lift"
      >
        {/* result (base) */}
        <Image
          src={AFTER.src}
          alt={AFTER.alt}
          fill
          className="object-cover"
          sizes="(max-width: 500px) 100vw, 460px"
        />

        {/* original (clipped overlay) */}
        <div
          className="absolute inset-y-0 left-0 overflow-hidden border-r-2 border-white"
          style={{ width: `${pos}%` }}
        >
          <div
            className="absolute inset-y-0 left-0"
            style={{ width: frameWidth ? `${frameWidth}px` : "100%" }}
          >
            <Image
              src={BEFORE.src}
              alt={BEFORE.alt}
              fill
              className="object-cover"
              sizes="(max-width: 500px) 100vw, 460px"
            />
          </div>
        </div>

        {/* scrim keeps the labels legible over any photo */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 z-[5] h-20 bg-gradient-to-b from-black/25 to-transparent"
        />

        <span className="absolute left-4 top-4 z-[15] rounded-full bg-white/90 px-3 py-1.5 text-[12px] font-semibold text-[#1c1b17] backdrop-blur">
          Before
        </span>
        <span className="absolute right-4 top-4 z-[15] rounded-full bg-sage px-3 py-1.5 text-[12px] font-semibold text-white">
          After try-on
        </span>

        {/* handle */}
        <div
          className="pointer-events-none absolute inset-y-0 z-10 w-0.5 bg-white/90"
          style={{ left: `${pos}%` }}
        >
          <div className="absolute left-1/2 top-1/2 grid h-12 w-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-[#1c1b17] shadow-lift">
            <span aria-hidden="true">↔</span>
          </div>
        </div>

        <input
          id={id}
          type="range"
          min={0}
          max={100}
          value={pos}
          onChange={(e) => setPos(Number(e.target.value))}
          aria-label="Reveal original vs try-on result"
          className="absolute inset-0 z-20 h-full w-full cursor-ew-resize opacity-0"
        />

      </div>
      {/* under the picture, so it never covers the outfit */}
      <div className="mx-auto mt-4 max-w-[460px] text-center">
        <p className="text-[15.5px] font-semibold text-ink">Pink embroidered suit, dupatta, tote bag and watch</p>
        <p className="mt-0.5 text-[13.5px] text-muted">A real TryOnU try-on, shown on an AI-generated model. Drag the line to compare.</p>
        <Button href="/try" size="lg" className="mt-4 w-full">
          Try it on yourself <span aria-hidden="true">→</span>
        </Button>
      </div>
    </div>
  );
}
