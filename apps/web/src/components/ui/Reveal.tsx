"use client";

import {
  useEffect,
  useRef,
  useState,
  type ElementType,
} from "react";

type RevealProps = {
  as?: ElementType;
  /** entrance direction */
  variant?: "up" | "left" | "right" | "scale";
  delay?: number;
  /** re-run the animation every time it scrolls back into view */
  repeat?: boolean;
  className?: string;
  children: React.ReactNode;
};

const VARIANT_CLASS: Record<NonNullable<RevealProps["variant"]>, string> = {
  up: "",
  left: "rv-left",
  right: "rv-right",
  scale: "rv-scale",
};

/**
 * Fade-and-move on scroll into view. Once the entrance animation ends we
 * drop it entirely (`is-settled`) so a lingering `animation-fill-mode`
 * never clamps `transform` and block :hover lifts on the same element.
 * Respects reduced-motion via CSS.
 */
export function Reveal({
  as,
  variant = "up",
  delay = 0,
  repeat = false,
  className = "",
  children,
}: RevealProps) {
  const Tag = (as ?? "div") as ElementType;
  const ref = useRef<HTMLElement | null>(null);
  const [shown, setShown] = useState(false);
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          if (!repeat) io.disconnect();
        } else if (repeat) {
          setShown(false);
          setSettled(false);
        }
      },
      { threshold: 0.14, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [repeat]);

  const state = settled ? "is-settled" : shown ? "is-visible" : "";

  return (
    <Tag
      ref={ref}
      onAnimationEnd={(e: React.AnimationEvent) => {
        if (!repeat && e.target === e.currentTarget) setSettled(true);
      }}
      className={`reveal ${VARIANT_CLASS[variant]} ${state} ${className}`}
      style={{ animationDelay: shown && !settled ? `${delay}ms` : undefined }}
    >
      {children}
    </Tag>
  );
}
