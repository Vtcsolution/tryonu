"use client";

import { useState } from "react";
import { markerItems } from "@/components/try/ResultMarkers";
import type { ResultPlacement } from "@/lib/api/types";

/** Every item on the finished photo, each shown close up.
 *
 * The result is a full-body photo, so a ring, a watch dial or the
 * embroidery on a neckline are a few dozen pixels in it — present, but
 * impossible to judge. These tiles crop the same photo to where the
 * pipeline actually put each item, so a shopper can see what they're
 * buying on themselves without hunting for it.
 *
 * They are crops of the result, not separate renders: nothing here is
 * generated, and a tile can only show an item the render really placed. */

const PADDING = 0.9; // extra context around the item's own box

export function ResultDetails({
  src,
  placements,
}: {
  src: string;
  placements: ResultPlacement[] | null | undefined;
}) {
  // the image's own proportions, so a square tile crops a square region
  // of the photo rather than a stretched one
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const items = markerItems(placements);
  if (items.length === 0) return null;

  return (
    <div className="mt-3">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt=""
        aria-hidden="true"
        className="hidden"
        onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
      />
      <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-faint">
        Every item, close up
      </p>
      <div className="flex gap-2.5 overflow-x-auto pb-1.5">
        {items.map((item, i) => {
          const [x0, y0, x1, y1] = item.box as number[];
          const tile = crop({ x0, y0, x1, y1 }, natural);
          return (
            <figure key={`${item.product_id ?? item.name}-${i}`} className="w-[108px] shrink-0">
              <div
                className="relative aspect-square overflow-hidden rounded-[12px] border border-line bg-paper-2"
                style={{
                  backgroundImage: `url(${src})`,
                  backgroundSize: tile.size,
                  backgroundPosition: tile.position,
                  backgroundRepeat: "no-repeat",
                }}
              >
                <span className="absolute left-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-sage text-[10px] font-semibold text-white">
                  {i + 1}
                </span>
              </div>
              <figcaption className="mt-1 line-clamp-2 text-[10.5px] leading-tight text-ink-soft">
                {item.name}
              </figcaption>
            </figure>
          );
        })}
      </div>
    </div>
  );
}

/** Background size/position that fills a square tile with the item's box.
 *
 * The box is in fractions of the image, which are not square unless the
 * image is — so the region is squared off in the image's own pixels
 * first, using its natural proportions. Before those load, a sensible
 * square guess keeps the tiles from jumping. */
function crop(
  box: { x0: number; y0: number; x1: number; y1: number },
  natural: { w: number; h: number } | null,
): { size: string; position: string } {
  const aspect = natural ? natural.w / natural.h : 1;
  const width = Math.max(0.02, (box.x1 - box.x0) * (1 + PADDING));
  const height = Math.max(0.02, (box.y1 - box.y0) * (1 + PADDING));

  // square in the image's pixels: a wide box grows vertically, a tall one
  // horizontally
  const side = Math.max(width, height / aspect);
  const w = Math.min(1, side);
  const h = Math.min(1, side * aspect);

  const centreX = (box.x0 + box.x1) / 2;
  const centreY = (box.y0 + box.y1) / 2;
  const left = clamp(centreX - w / 2, 0, 1 - w);
  const top = clamp(centreY - h / 2, 0, 1 - h);

  return {
    size: `${(100 / w).toFixed(2)}% ${(100 / h).toFixed(2)}%`,
    position: `${pct(left, w)}% ${pct(top, h)}%`,
  };
}

function pct(offset: number, span: number): string {
  return span >= 1 ? "0" : ((offset / (1 - span)) * 100).toFixed(2);
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}
