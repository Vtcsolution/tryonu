"use client";

import { useEffect, useRef, useState } from "react";
import { cardCrop } from "@/components/try/lookCrop";
import { resolveMediaUrl } from "@/lib/api/client";
import { shortLabel } from "@/components/try/labels";
import { markerItems } from "@/components/try/ResultMarkers";
import { ZoomableImage } from "@/components/try/ZoomableImage";
import type { ResultPlacement } from "@/lib/api/types";

/** The finished look, with the products beside it.
 *
 * Nothing is drawn on the photo. Names used to sit on the body they
 * described, which covered the one thing a customer is trying to look
 * at; they moved to the margins with a thin line joining each card to
 * its item, and the lines turned out to be the same complaint one step
 * removed — they cross the picture. So the photo is now just the photo,
 * and the cards sit either side of it in order, top to bottom.
 *
 * Each card shows the retailer's own photo of the product — the thing
 * the shopper is actually buying, shot properly, where a crop of our
 * render is a picture of our rendering of it and loses a watch face
 * entirely. A result saved before the product photo was recorded falls
 * back to the crop.
 *
 * Below the breakpoint the margins disappear and the cards become a
 * scrolling strip under the photo. */

// Up to this many, one column reads as a list beside the picture. More
// than this and a single column is taller than the photo it belongs to,
// so they open out to both sides — which is also how a labelled fashion
// plate has always been laid out.
const ONE_COLUMN_UP_TO = 4;

export function LookBoard({
  src,
  alt,
  placements,
  caption,
  children,
}: {
  src: string;
  alt: string;
  placements: ResultPlacement[] | null | undefined;
  caption?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const board = useRef<HTMLDivElement>(null);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  // Whether there is room for cards in the margins. A breakpoint can't
  // answer this: the board sits in one column of a grid, so a wide window
  // does not mean a wide board — and when it wasn't, the columns squeezed
  // the photo to nothing and spilled over the panel beside it.
  const [roomy, setRoomy] = useState(false);

  const items = markerItems(placements);
  const split = items.length > ONE_COLUMN_UP_TO ? Math.ceil(items.length / 2) : 0;
  const left = items.slice(0, split);
  const right = items.slice(split);

  useEffect(() => {
    const wrap = board.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => setRoomy(wrap.getBoundingClientRect().width >= 760));
    observer.observe(wrap);
    return () => observer.disconnect();
  }, []);

  const column = (list: ResultPlacement[], from: number) =>
    list.length === 0 ? null : (
      <div
        className={`w-[150px] shrink-0 flex-col justify-center gap-2.5 ${roomy ? "flex" : "hidden"}`}
      >
        {list.map((item, i) => (
          <Card
            key={`${item.product_id ?? item.name}-${from + i}`}
            item={item}
            number={from + i + 1}
            src={src}
            natural={natural}
          />
        ))}
      </div>
    );

  return (
    <div className="w-full">
      <div ref={board} className="relative flex items-center justify-center gap-4">
        {/* the picture's own proportions, so a square card crops a square
            region of it rather than a stretched one */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt=""
          aria-hidden="true"
          className="hidden"
          onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
        />
        {column(left, 0)}

        {/* as big as the board allows: the render is 1792x2400 and the
            detail a shopper is paying to see — stitching, a clasp, how a
            hem sits — does not survive being shown at a fraction of it */}
        <div className="w-full min-w-[260px] max-w-[680px] flex-1">
          <div
            className="relative overflow-hidden rounded-[26px] border border-line bg-paper-2 shadow-lift"
            // the frame takes the photo's own shape, so nothing is letterboxed
            style={{ aspectRatio: natural ? `${natural.w} / ${natural.h}` : "4 / 5" }}
          >
            <ZoomableImage src={src} alt={alt}>
              {children}
            </ZoomableImage>
            {caption}
          </div>
        </div>

        {column(right, split)}
      </div>
      {/* no margins to put cards in — they become a strip under the photo,
          so the products are never simply missing */}
      {!roomy && <LookStrip src={src} placements={placements} natural={natural} />}
    </div>
  );
}

function Card({
  item,
  number,
  src,
  natural,
}: {
  item: ResultPlacement;
  number: number;
  src: string;
  natural: { w: number; h: number } | null;
}) {
  return (
    <figure
      title={item.name}
      className="w-[150px] rounded-[14px] border border-line bg-surface p-1.5 shadow-sm"
    >
      <div
        className="relative aspect-square overflow-hidden rounded-[10px] bg-paper-2"
        style={productTile(item, src, natural)}
      />
      <figcaption className="mt-1 truncate px-0.5 text-[11px] font-medium leading-tight text-ink">
        {number}. {shortLabel(item.name, item.slot)}
      </figcaption>
    </figure>
  );
}

/** Where each item lands on the photo, and every item close up, for the
 * narrow layout that has no margins to put cards in. */
function LookStrip({
  src,
  placements,
  natural,
}: {
  src: string;
  placements: ResultPlacement[] | null | undefined;
  natural: { w: number; h: number } | null;
}) {
  const items = markerItems(placements);
  if (items.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-faint">Every item, close up</p>
      <div className="flex gap-2.5 overflow-x-auto pb-1.5">
        {items.map((item, i) => {
          return (
            <figure key={`${item.product_id ?? item.name}-${i}`} className="w-[108px] shrink-0">
              <div
                className="relative aspect-square overflow-hidden rounded-[12px] border border-line bg-paper-2"
                style={productTile(item, src, natural)}
              >
                <span className="absolute left-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-sage text-[10px] font-semibold text-white">
                  {i + 1}
                </span>
              </div>
              <figcaption className="mt-1 truncate text-[11px] font-medium leading-tight text-ink" title={item.name}>
                {shortLabel(item.name, item.slot)}
              </figcaption>
            </figure>
          );
        })}
      </div>
    </div>
  );
}

/** The card's picture: the retailer's photo of the product, or — for a
 * result saved before that was recorded — a close-up of where the render
 * put it. */
function productTile(
  item: ResultPlacement,
  src: string,
  natural: { w: number; h: number } | null,
): React.CSSProperties {
  const product = resolveMediaUrl(item.image_url);
  if (product) {
    return {
      backgroundImage: `url(${product})`,
      backgroundSize: "cover",
      backgroundPosition: "center",
      backgroundRepeat: "no-repeat",
    };
  }
  const [x0, y0, x1, y1] = item.box as number[];
  const tile = cardCrop({ x0, y0, x1, y1 }, natural);
  return {
    backgroundImage: `url(${src})`,
    backgroundSize: tile.size,
    backgroundPosition: tile.position,
    backgroundRepeat: "no-repeat",
  };
}
