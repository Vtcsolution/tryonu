"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { cardCrop } from "@/components/try/lookCrop";
import { resolveMediaUrl } from "@/lib/api/client";
import { shortLabel } from "@/components/try/labels";
import { markerItems } from "@/components/try/ResultMarkers";
import { ZoomableImage } from "@/components/try/ZoomableImage";
import type { ResultPlacement } from "@/lib/api/types";

/** The finished look with each item called out beside it.
 *
 * Labels used to sit on the photo, over the body they were describing —
 * on a full-body shot a bag on the forearm and a watch on the wrist put
 * their names across her arm, which is the one thing a customer is
 * trying to look at. The cards now live in the margins, joined to the
 * item by a thin line, so the photo stays a photo.
 *
 * Each card shows the retailer's own photo of the product — the thing
 * the shopper is actually buying, shot properly, where a crop of our
 * render is a picture of our rendering of it and loses a watch face
 * entirely. The render is what the numbered dot on the photo is for: it
 * says where that product ended up. A result saved before the product
 * photo was recorded falls back to the crop.
 *
 * Below the breakpoint the margins disappear, so the cards become a
 * scrolling strip under the photo and the lines are dropped. */

type Item = { item: ResultPlacement; number: number; x: number; y: number };
type Line = { x1: number; y1: number; x2: number; y2: number; bend: number };

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
  const frame = useRef<HTMLDivElement>(null);
  const cards = useRef(new Map<number, HTMLElement>());
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const previous = useRef<Line[]>([]);
  const [zoomed, setZoomed] = useState(false);
  // Whether there is room for cards in the margins. A breakpoint can't
  // answer this: the board sits in one column of a grid, so a wide window
  // does not mean a wide board — and when it wasn't, the columns squeezed
  // the photo to nothing and spilled over the panel beside it.
  const [roomy, setRoomy] = useState(false);

  const items: Item[] = markerItems(placements).map((item, index) => {
    const [x0, y0, x1, y1] = item.box as number[];
    return { item, number: index + 1, x: ((x0 + x1) / 2) * 100, y: ((y0 + y1) / 2) * 100 };
  });
  // left column takes what sits on the left of the body, right takes the
  // rest — the same split the eye expects from a labelled diagram
  const sorted = [...items].sort((a, b) => a.y - b.y);
  const left = sorted.filter((i) => i.x <= 50);
  const right = sorted.filter((i) => i.x > 50);

  const measure = useCallback(() => {
    const wrap = board.current;
    const box = frame.current?.getBoundingClientRect();
    if (!wrap || !box || !natural) return;
    const origin = wrap.getBoundingClientRect();

    // where the picture really sits inside its frame (object-contain
    // letterboxes it, so the frame's box is not the picture's box)
    const shown = Math.min(box.width / natural.w, box.height / natural.h);
    const pictureW = natural.w * shown;
    const pictureH = natural.h * shown;
    const pictureX = box.left - origin.left + (box.width - pictureW) / 2;
    const pictureY = box.top - origin.top + (box.height - pictureH) / 2;

    const drawn: Line[] = [];
    for (const { number, x, y } of items) {
      const card = cards.current.get(number)?.getBoundingClientRect();
      if (!card) continue;
      const onLeft = card.left - origin.left + card.width / 2 < pictureX + pictureW / 2;
      drawn.push({
        x1: card.left - origin.left + (onLeft ? card.width : 0),
        y1: card.top - origin.top + card.height / 2,
        x2: pictureX + (x / 100) * pictureW,
        y2: pictureY + (y / 100) * pictureH,
        bend: onLeft ? 18 : -18,
      });
    }
    // only re-render when the geometry really moved: this runs after every
    // layout, and setting an equal-but-new array would loop forever
    const same =
      drawn.length === previous.current.length &&
      drawn.every((line, i) => {
        const was = previous.current[i];
        return (
          Math.abs(line.x1 - was.x1) < 0.5 &&
          Math.abs(line.y1 - was.y1) < 0.5 &&
          Math.abs(line.x2 - was.x2) < 0.5 &&
          Math.abs(line.y2 - was.y2) < 0.5
        );
      });
    if (same) return;
    previous.current = drawn;
    setLines(drawn);
  }, [items, natural]);

  useLayoutEffect(measure);

  useEffect(() => {
    const wrap = board.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      setRoomy(wrap.getBoundingClientRect().width >= 760);
      measure();
    });
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [measure]);

  const column = (list: Item[], side: "left" | "right") => (
    <div className={`w-[150px] shrink-0 flex-col justify-center gap-2.5 ${roomy ? "flex" : "hidden"} ${side === "right" ? "items-start" : "items-end"}`}>
      {list.map(({ item, number }) => (
        <Card
          key={number}
          item={item}
          number={number}
          src={src}
          natural={natural}
          onMount={(node) => {
            if (node) cards.current.set(number, node);
            else cards.current.delete(number);
          }}
        />
      ))}
    </div>
  );

  return (
    <div className="w-full">
    <div ref={board} className="relative flex items-center justify-center gap-5">
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
      {column(left, "left")}

      {/* as big as the board allows: the render is 1024-2048px and the
          detail a shopper is paying to see — stitching, a clasp, how a
          hem sits — does not survive being shown at half that */}
      <div className="w-full min-w-[260px] max-w-[680px] flex-1">
        <div
          ref={frame}
          className="relative overflow-hidden rounded-[26px] border border-line bg-paper-2 shadow-lift"
          // the frame takes the photo's own shape, so nothing is
          // letterboxed and a leader line meets the picture's real edge
          style={{ aspectRatio: natural ? `${natural.w} / ${natural.h}` : "4 / 5" }}
        >
          <ZoomableImage
            src={src}
            alt={alt}
            onScaleChange={(scale) => setZoomed(scale > 1.001)}
            overlay={<Dots items={items} />}
          >
            {children}
          </ZoomableImage>
          {caption}
        </div>
      </div>

      {column(right, "right")}

      {/* the leader lines, drawn across the whole board. Hidden while the
          photo is zoomed, since the item is no longer where the line ends */}
      {roomy && !zoomed && lines.length > 0 && (
        <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
          {lines.map((line, i) => (
            <polyline
              key={i}
              points={`${line.x1},${line.y1} ${line.x1 + line.bend},${line.y1} ${line.x2},${line.y2}`}
              fill="none"
              stroke="rgba(255,255,255,0.75)"
              strokeWidth="1.25"
            />
          ))}
          {lines.map((line, i) => (
            <circle key={`dot-${i}`} cx={line.x2} cy={line.y2} r="3" fill="#fff" />
          ))}
        </svg>
      )}
    </div>
    {/* no margins to put cards in — they become a strip under the photo,
        so the close-ups are never simply missing */}
    {!roomy && <LookStrip src={src} placements={placements} natural={natural} />}
    </div>
  );
}

/** On the photo itself: only a small numbered dot, nothing that covers
 * what the shopper is trying to see. */
function Dots({ items }: { items: Item[] }) {
  return (
    <>
      {items.map(({ number, x, y }) => (
        <span
          key={number}
          className="absolute grid h-5 w-5 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-sage/90 text-[10px] font-semibold text-white ring-2 ring-white/80"
          style={{ left: `${x}%`, top: `${y}%` }}
        >
          {number}
        </span>
      ))}
    </>
  );
}

function Card({
  item,
  number,
  src,
  natural,
  onMount,
}: {
  item: ResultPlacement;
  number: number;
  src: string;
  natural: { w: number; h: number } | null;
  onMount: (node: HTMLElement | null) => void;
}) {
  return (
    <figure
      ref={onMount}
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
