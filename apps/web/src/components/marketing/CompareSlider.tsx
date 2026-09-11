"use client";

import Image from "next/image";
import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { PHOTOS } from "@/lib/media";

/**
 * Interactive before/after wipe. The two photos are illustrative stock
 * images for now (not the same person, no real try-on yet) — swap each
 * <Image> for the original photo / AI result when renders exist; the
 * wipe + handle logic is unchanged.
 */
export function CompareSlider() {
  const [pos, setPos] = useState(50);
  const id = useId();

  return (
    <div className="relative">
      <div className="relative h-[420px] overflow-hidden rounded-[28px] border border-line bg-paper-2 shadow-lift sm:h-[520px]">
        {/* result (base) */}
        <Image
          src={PHOTOS.lookBlueCoat.src}
          alt={`Try-on result — ${PHOTOS.lookBlueCoat.alt}`}
          fill
          priority
          className="object-cover object-[50%_20%]"
          sizes="(max-width: 1180px) 100vw, 1180px"
        />

        {/* original (clipped overlay) */}
        <div
          className="absolute inset-y-0 left-0 overflow-hidden border-r-2 border-white"
          style={{ width: `${pos}%` }}
        >
          <div
            className="absolute inset-y-0 left-0"
            style={{ width: "min(1180px, calc(100vw - 42px))" }}
          >
            <Image
              src={PHOTOS.portraitStudio.src}
              alt={`Original — ${PHOTOS.portraitStudio.alt}`}
              fill
              className="object-cover object-[50%_20%]"
              sizes="(max-width: 1180px) 100vw, 1180px"
            />
          </div>
        </div>

        {/* scrim keeps the labels legible over any photo */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 z-[5] h-20 bg-gradient-to-b from-black/25 to-transparent"
        />

        <span className="absolute left-4 top-4 z-[15] rounded-full bg-white/90 px-3 py-1.5 text-[11px] font-semibold text-[#1c1b17] backdrop-blur">
          Original
        </span>
        <span className="absolute right-4 top-4 z-[15] rounded-full bg-sage px-3 py-1.5 text-[11px] font-semibold text-white">
          Try-on result
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

        <div className="absolute bottom-4 right-4 z-[15] w-[220px] rounded-[18px] border border-line bg-surface/95 p-4 backdrop-blur">
          <p className="text-[11px] text-muted">Selected product</p>
          <p className="mb-3 mt-1 text-[14px] font-semibold text-ink">
            Sky Wrap Coat · $128.00
          </p>
          <Button
            href="https://www.example-retailer.com/sky-wrap-coat"
            size="sm"
            className="w-full"
          >
            Shop now <span aria-hidden="true">→</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
