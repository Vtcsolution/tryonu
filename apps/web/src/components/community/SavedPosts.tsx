"use client";

import Link from "next/link";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PostCard } from "@/components/community/PostCard";
import { community } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** /community/saved: the posts I bookmarked. */
export function SavedPosts() {
  const router = useRouter();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace("/sign-in?next=/community/saved");
  }, [isLoading, user, router]);
  const [removed, setRemoved] = useState<string[]>([]);
  const list = useInfiniteQuery({
    queryKey: ["community", "saved"],
    queryFn: ({ pageParam }) => community.saved(pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    enabled: !!user,
  });
  if (!user || list.isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  const posts = (list.data?.pages.flatMap((p) => p.posts) ?? []).filter((p) => !removed.includes(p.id));
  return (
    <section className="tu-container pb-10 pt-3 lg:py-12">
      <div className="mx-auto max-w-[640px]">
        <Link href="/community" className="inline-flex min-h-[40px] items-center rounded-full border border-line px-4 text-[14px] font-semibold text-ink-soft hover:text-ink max-lg:hidden">
          ← Community
        </Link>
        <h1 className="mt-4 font-display text-[clamp(28px,4vw,40px)] leading-tight text-ink max-lg:hidden">Saved posts</h1>
        <p className="mt-1 text-[15.5px] text-muted">Only you can see what you saved.</p>
        <div className="mt-6 space-y-6">
          {posts.length === 0 && (
            <p className="rounded-[20px] border border-dashed border-line p-10 text-center text-[16px] text-muted">
              Nothing saved yet. Tap the bookmark under any post to keep it here.
            </p>
          )}
          {posts.map((p) => (
            <PostCard key={p.id} post={p} onRemoved={() => setRemoved((r) => [...r, p.id])} />
          ))}
          {list.hasNextPage && (
            <button type="button" onClick={() => list.fetchNextPage()} className="tu-press min-h-[48px] w-full rounded-full border border-line-strong text-[15px] font-semibold text-ink">
              Show more
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
