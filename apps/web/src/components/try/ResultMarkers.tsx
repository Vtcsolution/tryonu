"use client";

import type { ResultPlacement } from "@/lib/api/types";

/** Numbered markers naming each item that was actually drawn on the photo.
 *
 * The try-on pipeline inspects every item and records the box it ended up
 * in, so these point at the real thing rather than a guess. Positions are
 * percentages of the picture, so they hold through zooming and panning.
 * Items the render never placed (a perfume, a bag it only matched) carry
 * no box and are left out here — the list beside the photo still shows
 * them, which is the honest split. */

export function markerItems(placements: ResultPlacement[] | null | undefined): ResultPlacement[] {
  return (placements ?? []).filter((p) => p.drawn && p.box && p.box.length === 4);
}

/** The number a placement is shown as, matching the list beside the photo. */
export function markerNumber(placements: ResultPlacement[] | null | undefined, productId: string): number | null {
  const index = markerItems(placements).findIndex((p) => p.product_id === productId);
  return index < 0 ? null : index + 1;
}

export function ResultMarkers({ placements }: { placements: ResultPlacement[] | null | undefined }) {
  const items = markerItems(placements);
  if (items.length === 0) return null;

  return (
    <>
      {items.map((item, i) => {
        const [x0, y0, x1, y1] = item.box as number[];
        const x = ((x0 + x1) / 2) * 100;
        const y = ((y0 + y1) / 2) * 100;
        // a marker near the right edge opens to the left, so its name
        // doesn't run off the photo
        const flip = x > 62;
        return (
          <div
            key={`${item.product_id ?? item.name}-${i}`}
            className="absolute flex items-center gap-1.5"
            style={{
              left: `${x}%`,
              top: `${y}%`,
              transform: `translate(${flip ? "-100%" : "0"}, -50%)`,
              flexDirection: flip ? "row-reverse" : "row",
            }}
          >
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-sage text-[11px] font-semibold text-white shadow-[0_1px_6px_rgba(0,0,0,0.45)] ring-2 ring-white/70">
              {i + 1}
            </span>
            <span className="max-w-[46vw] truncate rounded-full bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur-sm md:max-w-[220px]">
              {item.name}
            </span>
          </div>
        );
      })}
    </>
  );
}
