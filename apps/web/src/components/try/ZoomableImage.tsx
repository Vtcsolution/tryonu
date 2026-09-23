"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** A try-on result you can look at closely: the whole point of the render is
 * detail a customer wants to inspect — the stitching on a kurta, whether a
 * watch sits right on the wrist — and at the size the card shows, they
 * can't. Zoom with the buttons, the wheel, a pinch or a double-click, then
 * drag to move around. */

const MIN = 1;
const MAX = 5;
const STEP = 1.6; // per button press / double-click

type Point = { x: number; y: number };

export function ZoomableImage({
  src,
  alt,
  overlay,
  children,
}: {
  src: string;
  alt: string;
  /** Drawn on top of the photo itself, in the photo's own coordinates
   * (percentages of the picture, not of the frame) — so markers stay on
   * the item they point at through zooming and panning. */
  overlay?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const [picture, setPicture] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const natural = useRef<{ w: number; h: number } | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 });
  const drag = useRef<{ from: Point; at: Point } | null>(null);
  const pinch = useRef<{ distance: number; scale: number } | null>(null);
  // in state, not just the ref: the transition has to be off for the frame
  // the drag starts on, or the photo lags a finger behind
  const [moving, setMoving] = useState(false);
  const zoomed = scale > 1.001;

  /** Keep the image covering the frame: panning may never expose a gap. */
  const clamp = useCallback((next: Point, atScale: number): Point => {
    const box = frame.current?.getBoundingClientRect();
    if (!box) return next;
    const room = { x: (box.width * (atScale - 1)) / 2, y: (box.height * (atScale - 1)) / 2 };
    return {
      x: Math.min(room.x, Math.max(-room.x, next.x)),
      y: Math.min(room.y, Math.max(-room.y, next.y)),
    };
  }, []);

  /** Zoom around a point of the frame (the cursor, or the middle), so what
   * you are looking at stays under the cursor instead of sliding away. */
  const zoomTo = useCallback(
    (next: number, at?: Point) => {
      const box = frame.current?.getBoundingClientRect();
      const target = Math.min(MAX, Math.max(MIN, next));
      setScale((current) => {
        if (!box || target === current) return target;
        const anchor = at ?? { x: box.width / 2, y: box.height / 2 };
        const fromCentre = { x: anchor.x - box.width / 2, y: anchor.y - box.height / 2 };
        setOffset((o) =>
          target === MIN
            ? { x: 0, y: 0 }
            : clamp(
                {
                  x: fromCentre.x - ((fromCentre.x - o.x) * target) / current,
                  y: fromCentre.y - ((fromCentre.y - o.y) * target) / current,
                },
                target,
              ),
        );
        return target;
      });
    },
    [clamp],
  );

  const pointIn = (e: { clientX: number; clientY: number }): Point | undefined => {
    const box = frame.current?.getBoundingClientRect();
    return box ? { x: e.clientX - box.left, y: e.clientY - box.top } : undefined;
  };

  // Non-passive so the page doesn't scroll under a zoom gesture. React's
  // onWheel is passive, hence the manual listener.
  useEffect(() => {
    const node = frame.current;
    if (!node) return;
    const onWheel = (e: WheelEvent) => {
      // At 1x a plain wheel is someone scrolling the page past the photo —
      // only take it over once they've zoomed in, or if they hold ctrl/⌘
      // (what a trackpad pinch sends).
      if (!zoomed && !e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      zoomTo(scale * (e.deltaY < 0 ? 1.12 : 1 / 1.12), pointIn(e));
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [scale, zoomed, zoomTo]);

  const onPointerDown = (e: React.PointerEvent) => {
    if (!zoomed || e.pointerType === "touch") return;
    const at = pointIn(e);
    if (!at) return;
    drag.current = { from: at, at: offset };
    setMoving(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const held = drag.current;
    const at = pointIn(e);
    if (!held || !at) return;
    setOffset(clamp({ x: held.at.x + (at.x - held.from.x), y: held.at.y + (at.y - held.from.y) }, scale));
  };

  const endDrag = () => {
    drag.current = null;
    setMoving(false);
  };

  const touchDistance = (t: React.TouchList) =>
    Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);

  const onTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      pinch.current = { distance: touchDistance(e.touches), scale };
      setMoving(true);
    } else if (e.touches.length === 1 && zoomed) {
      const at = pointIn(e.touches[0]);
      if (at) {
        drag.current = { from: at, at: offset };
        setMoving(true);
      }
    }
  };

  const onTouchMove = (e: React.TouchEvent) => {
    if (e.touches.length === 2 && pinch.current) {
      e.preventDefault();
      const { distance, scale: from } = pinch.current;
      const box = frame.current?.getBoundingClientRect();
      const middle =
        box && {
          x: (e.touches[0].clientX + e.touches[1].clientX) / 2 - box.left,
          y: (e.touches[0].clientY + e.touches[1].clientY) / 2 - box.top,
        };
      zoomTo((from * touchDistance(e.touches)) / distance, middle || undefined);
      return;
    }
    const held = drag.current;
    if (!held || e.touches.length !== 1) return;
    const at = pointIn(e.touches[0]);
    if (!at) return;
    e.preventDefault(); // panning the photo, not the page
    setOffset(clamp({ x: held.at.x + (at.x - held.from.x), y: held.at.y + (at.y - held.from.y) }, scale));
  };

  const onTouchEnd = (e: React.TouchEvent) => {
    if (e.touches.length < 2) pinch.current = null;
    if (e.touches.length === 0) {
      drag.current = null;
      setMoving(false);
    }
  };

  /** Where the photo actually sits inside the frame: object-contain
   * letterboxes it, so the frame's box is not the picture's box. */
  const measure = useCallback(() => {
    const box = frame.current?.getBoundingClientRect();
    const size = natural.current;
    if (!box || !size || !size.w || !size.h) return;
    const shown = Math.min(box.width / size.w, box.height / size.h);
    const width = size.w * shown;
    const height = size.h * shown;
    setPicture({ left: (box.width - width) / 2, top: (box.height - height) / 2, width, height });
  }, []);

  useEffect(() => {
    const node = frame.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [measure]);

  const reset = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  // a new result (another angle, another try-on) starts at 1x
  useEffect(reset, [src]);

  const control =
    "grid h-9 w-9 place-items-center rounded-full bg-surface/90 text-[17px] leading-none text-ink shadow-sm " +
    "transition-colors hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <div
      ref={frame}
      className="absolute inset-0 overflow-hidden"
      style={{ touchAction: zoomed ? "none" : "pan-y" }}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      <div
        className="absolute inset-0"
        style={{
          transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          transformOrigin: "center",
          transition: moving ? "none" : "transform 0.18s cubic-bezier(0.22,1,0.36,1)",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          draggable={false}
          onLoad={(e) => {
            natural.current = { w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight };
            measure();
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onDoubleClick={(e) => (zoomed ? reset() : zoomTo(2.6, pointIn(e)))}
          className="h-full w-full select-none object-contain"
          style={{ cursor: zoomed ? (moving ? "grabbing" : "grab") : "zoom-in" }}
        />
        {overlay && picture && (
          <div
            className="pointer-events-none absolute"
            style={{ left: picture.left, top: picture.top, width: picture.width, height: picture.height }}
          >
            {overlay}
          </div>
        )}
      </div>

      {children}

      <div className="absolute bottom-14 right-3 z-10 flex flex-col gap-1.5">
        <button type="button" onClick={() => zoomTo(scale * STEP)} disabled={scale >= MAX} className={control} aria-label="Zoom in">
          +
        </button>
        <button type="button" onClick={() => zoomTo(scale / STEP)} disabled={!zoomed} className={control} aria-label="Zoom out">
          −
        </button>
        <button
          type="button"
          onClick={reset}
          disabled={!zoomed}
          className={`${control} text-[11px] font-semibold`}
          aria-label="Reset zoom"
        >
          {zoomed ? `${scale.toFixed(1)}×` : "1×"}
        </button>
      </div>
    </div>
  );
}
