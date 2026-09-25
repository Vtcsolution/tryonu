/** Which part of the result photo one callout card shows.
 *
 * A card is a close-up: its job is to show a shopper that this item, the
 * one they picked, is really on the photo and what it looks like there.
 * It is not a second copy of the picture.
 *
 * It used to become one. Every box was padded out by 90% in each
 * direction before being squared off, and a dress's box is most of a
 * full-body photo to begin with — live, a salwar kameez came back at
 * x 0.00-0.69, y 0.20-1.00, which padded past the frame and clamped to
 * all of it. Three cards beside a bridal look were three copies of the
 * render, each with the item somewhere inside it, too small to see.
 */

const PADDING = 0.25; // a little room around the item, in its own size
// A watch is ~3% of a full-body photo. Cropping to just that and blowing
// it up to a 150px card gives a blur with no landmarks — the wrist around
// it is what makes it readable, so no crop goes tighter than this.
const MIN_CROP = 0.16;
// ...and none goes wider than this, however big the item is.
const MAX_CROP = 0.42;

export type Box = { x0: number; y0: number; x1: number; y1: number };

/** Background size/position that fills a square tile with the item's box.
 *
 * The box is in fractions of the image, which are not square unless the
 * image is — so the region is squared off in the image's own pixels
 * first, using its natural proportions. */
export function cardCrop(
  box: Box,
  natural: { w: number; h: number } | null,
): { size: string; position: string; width: number; height: number } {
  const aspect = natural ? natural.w / natural.h : 1;
  const width = (box.x1 - box.x0) * (1 + PADDING);
  const height = (box.y1 - box.y0) * (1 + PADDING);
  const side = clamp(Math.max(width, height / aspect), MIN_CROP, MAX_CROP);
  const w = Math.min(1, side);
  const h = Math.min(1, side * aspect);

  const left = clamp((box.x0 + box.x1) / 2 - w / 2, 0, 1 - w);
  // An item taller than the card shows its upper part, not its middle:
  // on a floor-length dress that is the neckline and the bodice — what
  // tells you which dress it is — where the middle is an acre of skirt.
  // Not the very top: a garment's box reaches past the shoulders (live,
  // a salwar kameez was recorded from y 0.046, above the face), and a
  // card of someone's chin is not a card of the dress.
  const tall = box.y1 - box.y0;
  const top = clamp(box.y0 + (tall - h) * (h < tall ? 0.2 : 0.5), 0, 1 - h);
  return {
    size: `${(100 / w).toFixed(2)}% ${(100 / h).toFixed(2)}%`,
    position: `${pct(left, w)}% ${pct(top, h)}%`,
    width: w,
    height: h,
  };
}

function pct(offset: number, span: number): string {
  return span >= 1 ? "0" : ((offset / (1 - span)) * 100).toFixed(2);
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}
