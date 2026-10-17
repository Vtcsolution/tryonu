"use client";

import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Avatar, PostCard } from "@/components/community/PostCard";
import { COMMUNITY_RULES } from "@/components/community/PostToCommunity";
import { Button } from "@/components/ui/Button";
import { community } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** /community: looks members shared. Members only; visitors see what it is and join. */
export function CommunityFeed() {
  const { user, isLoading } = useSession();
  const [tab, setTab] = useState<"for_you" | "following">("for_you");
  const me = useQuery({ queryKey: ["community", "me"], queryFn: community.me, enabled: !!user });
  const feed = useInfiniteQuery({
    queryKey: ["community", "feed", tab],
    queryFn: ({ pageParam }) => community.feed(tab, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    enabled: !!user,
  });
  const [removed, setRemoved] = useState<string[]>([]);

  if (isLoading) {
    return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  }
  if (!user) {
    return (
      <section className="tu-container py-14 md:py-20">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-[13px] font-semibold uppercase tracking-[0.16em] text-sage-deep">TryOnU community</p>
          <h1 className="mt-2 font-display text-[clamp(32px,5vw,52px)] leading-[1.05] text-ink">
            Share your looks. <em>Get inspired.</em>
          </h1>
          <p className="mt-4 text-[17.5px] leading-relaxed text-ink-soft">
            See the outfits other members tried on, like and comment, follow the people whose style you love, and try any look on
            yourself in one click.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button href="/sign-up?next=/community" size="lg">Join the community</Button>
            <Button href="/sign-in?next=/community" size="lg" variant="outline">Sign in</Button>
          </div>
          <p className="mt-4 text-[14px] text-muted">The community is for members only, to keep everyone&apos;s photos safe.</p>
        </div>
      </section>
    );
  }

  const posts = (feed.data?.pages.flatMap((p) => p.posts) ?? []).filter((p) => !removed.includes(p.id));
  return (
    <section className="tu-container py-8 md:py-12">
      <div className="mx-auto grid max-w-[1100px] gap-8 lg:grid-cols-[minmax(0,640px)_minmax(0,1fr)]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-[clamp(28px,4vw,40px)] leading-tight text-ink">Community</h1>
            <div role="tablist" aria-label="Feed" className="flex rounded-full border border-line p-1">
              {(
                [
                  ["for_you", "For you"],
                  ["following", "Following"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                  className={`min-h-[38px] rounded-full px-4 text-[14.5px] font-semibold ${tab === id ? "bg-ink text-surface" : "text-ink-soft hover:text-ink"}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 space-y-6">
            {feed.isLoading &&
              Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-[520px] animate-pulse rounded-[22px] bg-paper-2" />)}
            {!feed.isLoading && posts.length === 0 && (
              <div className="rounded-[22px] border border-dashed border-line p-10 text-center">
                {tab === "following" ? (
                  <p className="text-[16px] text-muted">Follow members whose looks you like, and their new posts show up here.</p>
                ) : (
                  <p className="text-[16px] text-muted">No looks yet. Be the first: make a try-on and press “Post to community”.</p>
                )}
                <Button href="/try" size="md" className="mt-5">Make a look</Button>
              </div>
            )}
            {posts.map((p) => (
              <PostCard key={p.id} post={p} onRemoved={() => setRemoved((r) => [...r, p.id])} />
            ))}
            {feed.hasNextPage && (
              <button
                type="button"
                onClick={() => feed.fetchNextPage()}
                disabled={feed.isFetchingNextPage}
                className="tu-press min-h-[48px] w-full rounded-full border border-line-strong text-[15px] font-semibold text-ink"
              >
                {feed.isFetchingNextPage ? "Loading…" : "Show more looks"}
              </button>
            )}
          </div>
        </div>

        <aside className="hidden lg:block">
          <div className="sticky top-24 space-y-5">
            {me.data && (
              <Link href={`/u/${me.data.handle}`} className="flex items-center gap-3 rounded-[20px] border border-line bg-surface p-4 hover:border-line-strong">
                <Avatar name={me.data.name} handle={me.data.handle} url={me.data.avatar_url} size={48} />
                <span className="min-w-0">
                  <span className="block truncate text-[16px] font-semibold text-ink">{me.data.name || me.data.handle}</span>
                  <span className="block text-[13.5px] text-muted">
                    @{me.data.handle} · {me.data.posts} posts · {me.data.followers} followers
                  </span>
                </span>
              </Link>
            )}
            <div className="rounded-[20px] border border-line bg-surface p-5">
              <p className="text-[16px] font-semibold text-ink">Share your look</p>
              <p className="mt-1 text-[14.5px] text-muted">Make a try-on, then press “Post to community” on the result or on any saved look.</p>
              <Button href="/try" size="md" className="mt-4 w-full">Make a look</Button>
            </div>
            <div className="rounded-[20px] border border-line bg-surface p-5">
              <p className="text-[15px] font-semibold text-ink">Community rules</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-[14px] text-ink-soft">
                {COMMUNITY_RULES.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
