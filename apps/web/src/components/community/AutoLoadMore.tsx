"use client";

import { useEffect, useRef } from "react";

/** Endless scrolling: loads the next page by itself a little before the
 * reader reaches the end, with a small spinner while it comes in. */
export function AutoLoadMore({ hasMore, loading, onMore }: { hasMore: boolean; loading: boolean; onMore: () => void }) {
  const spot = useRef<HTMLDivElement>(null);
  const more = useRef(onMore);
  more.current = onMore;
  useEffect(() => {
    const el = spot.current;
    if (!el || !hasMore) return;
    const seen = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && !loading) more.current();
      },
      { rootMargin: "800px 0px" },
    );
    seen.observe(el);
    return () => seen.disconnect();
  }, [hasMore, loading]);
  if (!hasMore) return null;
  return (
    <div ref={spot} className="flex justify-center py-6" aria-live="polite">
      {loading && <span className="h-7 w-7 animate-spin rounded-full border-2 border-line-strong border-t-sage" aria-label="Loading more" />}
    </div>
  );
}
