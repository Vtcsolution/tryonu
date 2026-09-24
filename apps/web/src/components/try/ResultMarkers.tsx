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

/** Where each marker sits, after moving overlapping ones apart.
 *
 * Items land where they land: a bag on the forearm and a watch on the
 * wrist are inches apart on a body, and their labels sat on top of each
 * other, unreadable and hanging off the picture. Anything sharing a band
 * of the photo is spread down the frame, keeping its own number with it. */
function laidOut(items: ResultPlacement[]) {
  const MIN_GAP = 9; // percent of the picture's height between two labels
  const placed = items
    .map((item, index) => {
      const [x0, y0, x1, y1] = item.box as number[];
      return { item, number: index + 1, x: ((x0 + x1) / 2) * 100, y: ((y0 + y1) / 2) * 100 };
    })
    .sort((a, b) => a.y - b.y);

  let lowest = -Infinity;
  for (const marker of placed) {
    if (marker.y - lowest < MIN_GAP) marker.y = lowest + MIN_GAP;
    lowest = marker.y;
  }
  // if pushing down ran past the bottom, lift the whole column back up
  const overflow = placed.length ? placed[placed.length - 1].y - 94 : 0;
  if (overflow > 0) for (const marker of placed) marker.y -= overflow;

  return placed.map((marker) => ({ ...marker, y: Math.min(94, Math.max(6, marker.y)) }));
}

export function ResultMarkers({ placements }: { placements: ResultPlacement[] | null | undefined }) {
  const items = markerItems(placements);
  if (items.length === 0) return null;

  return (
    <>
      {laidOut(items).map(({ item, number, x, y }) => {
        // a marker past the middle opens to the left, so its name stays on
        // the picture instead of running off the edge
        const flip = x > 55;
        return (
          <div
            key={`${item.product_id ?? item.name}-${number}`}
            className="absolute flex items-center gap-1.5"
            style={{
              left: `${Math.min(92, Math.max(8, x))}%`,
              top: `${y}%`,
              transform: `translate(${flip ? "-100%" : "0"}, -50%)`,
              flexDirection: flip ? "row-reverse" : "row",
              maxWidth: flip ? `${Math.min(92, Math.max(8, x))}%` : `${100 - Math.min(92, Math.max(8, x))}%`,
            }}
          >
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-sage text-[11px] font-semibold text-white shadow-[0_1px_6px_rgba(0,0,0,0.45)] ring-2 ring-white/70">
              {number}
            </span>
            <span className="truncate rounded-full bg-black/65 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur-sm">
              {item.name}
            </span>
          </div>
        );
      })}
    </>
  );
}
