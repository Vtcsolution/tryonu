"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/Button";
import { mediaThumb, resolveMediaUrl } from "@/lib/api/client";
import { tryon, type GalleryItem } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** Every finished try-on, newest first, each in its own shape (never cropped).
 *  A page at a time, so a member with hundreds of looks still gets a fast page. */
export function GalleryPage() {
  const { user, isLoading } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState<GalleryItem | null>(null);
  const looks = useInfiniteQuery({
    queryKey: ["tryon", "gallery"],
    queryFn: ({ pageParam }) => tryon.gallery(pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    enabled: !!user,
  });

  useEffect(() => {
    if (!isLoading && !user) router.replace(`/sign-in?next=${encodeURIComponent("/gallery")}`);
  }, [isLoading, user, router]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const items = looks.data?.pages.flatMap((p) => p.items) ?? [];
  const total = looks.data?.pages[0]?.total ?? 0;

  return (
    <section className="mx-auto tu-container py-10 md:py-14">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-[34px] leading-tight text-ink md:text-[42px]">My looks</h1>
          <p className="mt-1 text-[16px] text-muted">
            {total > 0 ? `All ${total} of your try-ons, saved for you.` : "Every look you try on is saved here."}
          </p>
        </div>
        <Button href="/try" size="md">
          Try a new look <span aria-hidden="true">→</span>
        </Button>
      </div>

      {(isLoading || looks.isLoading) && (
        <div className="mt-8 columns-2 gap-4 md:columns-3 lg:columns-4" aria-hidden="true">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="mb-4 aspect-[3/4] animate-pulse rounded-[18px] bg-paper-2" />
          ))}
        </div>
      )}
      {looks.isError && <p className="mt-8 text-[15px] text-[#a4553f]">Your looks couldn&apos;t load. Please refresh the page.</p>}
      {looks.isSuccess && items.length === 0 && (
        <div className="mt-8 rounded-[22px] border border-dashed border-line-strong p-10 text-center">
          <p className="text-[17px] text-ink">You haven&apos;t tried anything on yet.</p>
          <Link href="/looks" className="mt-2 inline-block text-[15.5px] font-semibold text-sage-deep hover:underline">
            Pick a Ready look to start
          </Link>
        </div>
      )}

      <div className="mt-8 columns-2 gap-4 md:columns-3 lg:columns-4">
        {items.map((look) => (
          <button
            key={look.job_id}
            type="button"
            onClick={() => setOpen(look)}
            className="mb-4 block w-full break-inside-avoid overflow-hidden rounded-[18px] border border-line bg-paper-2 text-left transition-shadow hover:shadow-lift"
            aria-label={`Open your look: ${look.what}`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={mediaThumb(look.image_url, 600)}
              alt={look.what}
              width={look.width ?? undefined}
              height={look.height ?? undefined}
              loading="lazy"
              decoding="async"
              className="block h-auto w-full"
            />
          </button>
        ))}
      </div>

      {looks.hasNextPage && (
        <div className="mt-6 text-center">
          <Button variant="outline" size="md" disabled={looks.isFetchingNextPage} onClick={() => looks.fetchNextPage()}>
            {looks.isFetchingNextPage ? "Loading…" : "Show more"}
          </Button>
        </div>
      )}

      {open &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Your look"
            className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-3 bg-black/85 p-4"
            onMouseDown={(e) => e.target === e.currentTarget && setOpen(null)}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={resolveMediaUrl(open.image_url)} alt={open.what} className="max-h-[82vh] max-w-full rounded-xl object-contain" />
            <div className="flex flex-wrap items-center justify-center gap-2">
              <Link href={`/try?job=${open.job_id}`} className="inline-flex min-h-[44px] items-center rounded-full bg-white px-5 text-[15px] font-semibold text-[#1c1b17]">
                Shop this look
              </Link>
              <button type="button" onClick={() => setOpen(null)} className="min-h-[44px] rounded-full border border-white/60 px-5 text-[15px] font-semibold text-white">
                Close
              </button>
            </div>
          </div>,
          document.body,
        )}
    </section>
  );
}
