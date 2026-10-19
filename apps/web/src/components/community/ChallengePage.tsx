"use client";

import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CreatePost } from "@/components/community/CreatePost";
import { Medal, PLACE, TrophyIcon, timeLeft } from "@/components/community/extras";
import { Avatar, PostCard } from "@/components/community/PostCard";
import { Button } from "@/components/ui/Button";
import { community, type Challenge } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

function useMembersOnly(next: string) {
  const router = useRouter();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace(`/sign-in?next=${encodeURIComponent(next)}`);
  }, [isLoading, user, router, next]);
  return user;
}

const fmt = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** /community/challenges/<id>: the theme, prizes, time left, the winners, and the entries (most liked first). */
export function ChallengePage({ id }: { id: string }) {
  const user = useMembersOnly(`/community/challenges/${id}`);
  const [joining, setJoining] = useState(false);
  const q = useInfiniteQuery({
    queryKey: ["community", "challenge", id],
    queryFn: ({ pageParam }) => community.challenge(id, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => last.entries.next_offset ?? undefined,
    enabled: !!user,
  });

  if (!user || q.isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  if (q.isError || !q.data) {
    return (
      <section className="tu-container py-20 text-center">
        <p className="font-display text-[26px] text-ink">This challenge isn&apos;t here anymore</p>
        <Button href="/community" size="md" className="mt-5">Back to the community</Button>
      </section>
    );
  }
  const ch = q.data.pages[0].challenge;
  const posts = q.data.pages.flatMap((p) => p.entries.posts);
  return (
    <section className="tu-container py-8 md:py-12">
      <div className="mx-auto max-w-[680px]">
        <Link href="/community/challenges" className="inline-flex min-h-[40px] items-center rounded-full border border-line px-4 text-[14px] font-semibold text-ink-soft hover:text-ink">
          ← All challenges
        </Link>

        <header className="mt-4 rounded-[22px] border border-[#c9a13b]/40 bg-gradient-to-br from-[#c9a13b]/[0.14] via-surface to-sage-tint/30 p-5 md:p-6">
          <p className="flex items-center gap-1.5 text-[12.5px] font-semibold uppercase tracking-[0.12em] text-[#8a6d1f]">
            <TrophyIcon size={15} color="#a8842a" /> Style challenge · {ch.state === "ended" ? `Ended ${fmt(ch.ends_at)}` : timeLeft(ch)}
          </p>
          <h1 className="mt-1 font-display text-[clamp(28px,5vw,40px)] leading-tight text-ink">{ch.title}</h1>
          {ch.description && <p className="mt-2 whitespace-pre-wrap text-[16px] text-ink-soft">{ch.description}</p>}
          <p className="mt-2 text-[14px] text-muted">
            {fmt(ch.starts_at)} – {fmt(ch.ends_at)} · {ch.entries} {ch.entries === 1 ? "entry" : "entries"}
            {ch.sponsor && (
              <>
                {" "}· Sponsored by{" "}
                <Link href={`/stores/${ch.sponsor.slug}`} className="font-semibold text-ink hover:underline">
                  {ch.sponsor.name}
                </Link>
              </>
            )}
          </p>

          <div className="mt-4 grid grid-cols-3 gap-2">
            {ch.prizes.map((p, i) => (
              <div key={i} className="rounded-xl border border-line bg-surface p-3 text-center">
                <div className="flex justify-center">
                  <Medal place={i + 1} size={26} />
                </div>
                <p className="mt-1.5 text-[15px] font-semibold text-ink">{p ? `${p} credits` : "—"}</p>
                <p className="text-[12.5px] text-muted">{PLACE[i + 1]} place</p>
              </div>
            ))}
          </div>

          <ol className="mt-4 space-y-1 text-[14px] text-ink-soft">
            <li>1. Make a try-on look (or use one you already made).</li>
            <li>2. Post it with “Enter the challenge” ticked. One entry per member.</li>
            <li>3. The looks with the most likes from other members win when the time is up.</li>
          </ol>

          {ch.state === "live" && (
            <div className="mt-4 flex flex-wrap gap-2">
              {ch.my_entry_post_id ? (
                <Link href={`/community/post/${ch.my_entry_post_id}`} className="inline-flex min-h-[46px] items-center rounded-full border border-line-strong bg-surface px-5 text-[15px] font-semibold text-ink">
                  ✓ You&apos;re in · View my entry
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => setJoining(true)}
                  className="tu-press inline-flex min-h-[46px] items-center rounded-full bg-[#b08a2e] px-6 text-[15.5px] font-semibold text-white hover:bg-[#9a7822]"
                >
                  Join the challenge
                </button>
              )}
              <Link href="/try" className="inline-flex min-h-[46px] items-center rounded-full border border-line-strong bg-surface px-5 text-[15px] font-semibold text-ink">
                Make a new look
              </Link>
            </div>
          )}
          {ch.state === "upcoming" && <p className="mt-4 text-[15px] font-semibold text-ink">{timeLeft(ch)}. Get your look ready!</p>}
        </header>
        {joining && <CreatePost variant="none" startOpen extras={{ challenge_id: ch.id }} onClosed={() => setJoining(false)} />}

        {ch.state === "ended" && (
          <div className="mt-6 rounded-[22px] border border-line bg-surface p-5">
            <h2 className="text-[18px] font-semibold text-ink">Winners</h2>
            {ch.winners.length === 0 ? (
              <p className="mt-2 text-[15px] text-muted">No winners this time: no entry got a like from another member.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {ch.winners.map((w) => (
                  <Link
                    key={w.place}
                    href={w.post_id ? `/community/post/${w.post_id}` : `/u/${w.author.handle}`}
                    className="flex items-center gap-3 rounded-xl border border-line p-3 hover:border-line-strong"
                  >
                    <Medal place={w.place} size={28} />
                    <Avatar name={w.author.name} handle={w.author.handle} url={w.author.avatar_url} size={40} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15.5px] font-semibold text-ink">{w.author.name || `@${w.author.handle}`}</span>
                      <span className="block text-[13px] text-muted">
                        {PLACE[w.place]} place · {w.likes} {w.likes === 1 ? "like" : "likes"}
                      </span>
                    </span>
                    {w.credits > 0 && <span className="text-[14px] font-semibold text-sage-deep">+{w.credits} credits</span>}
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}

        <h2 className="mt-8 text-[18px] font-semibold text-ink">
          {ch.state === "ended" ? "All entries" : "Entries"} <span className="font-normal text-muted">· most liked first</span>
        </h2>
        <div className="mt-4 space-y-6">
          {posts.length === 0 && (
            <p className="rounded-[20px] border border-dashed border-line p-10 text-center text-[16px] text-muted">
              {ch.state === "live" ? "No entries yet. Be the first!" : "No entries."}
            </p>
          )}
          {posts.map((p, i) => (
            <div key={p.id}>
              {ch.state === "ended"
                ? p.award && (
                    <p className="mb-2 flex items-center gap-2 text-[14px] font-semibold text-ink">
                      <Medal place={p.award} size={20} /> {PLACE[p.award]} place
                    </p>
                  )
                : ch.state === "live" &&
                  i < 3 &&
                  p.like_count > 0 && (
                    <p className="mb-2 flex items-center gap-2 text-[14px] font-semibold text-ink">
                      <Medal place={i + 1} size={20} /> {PLACE[i + 1]} right now
                    </p>
                  )}
              <PostCard post={p} />
            </div>
          ))}
          {q.hasNextPage && (
            <button
              type="button"
              onClick={() => q.fetchNextPage()}
              disabled={q.isFetchingNextPage}
              className="tu-press min-h-[48px] w-full rounded-full border border-line-strong text-[15px] font-semibold text-ink"
            >
              {q.isFetchingNextPage ? "Loading…" : "Show more entries"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

/** /community/challenges: running now, coming up, and past winners. */
export function ChallengesList() {
  const user = useMembersOnly("/community/challenges");
  const q = useQuery({ queryKey: ["community", "challenges"], queryFn: community.challenges, enabled: !!user });
  if (!user || q.isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  const groups: [string, Challenge[]][] = [
    ["Running now", q.data?.live ?? []],
    ["Coming up", q.data?.upcoming ?? []],
    ["Finished", q.data?.ended ?? []],
  ];
  const none = groups.every(([, list]) => list.length === 0);
  return (
    <section className="tu-container py-8 md:py-12">
      <div className="mx-auto max-w-[760px]">
        <Link href="/community" className="inline-flex min-h-[40px] items-center rounded-full border border-line px-4 text-[14px] font-semibold text-ink-soft hover:text-ink">
          ← Community
        </Link>
        <h1 className="mt-4 font-display text-[clamp(28px,4vw,40px)] leading-tight text-ink">Style challenges</h1>
        <p className="mt-1 text-[16px] text-muted">A new theme every week. The most liked looks win free credits.</p>
        {none && <p className="mt-8 rounded-[20px] border border-dashed border-line p-10 text-center text-[16px] text-muted">The first challenge is coming soon.</p>}
        {groups.map(([label, list]) =>
          list.length ? (
            <div key={label} className="mt-8">
              <h2 className="text-[18px] font-semibold text-ink">{label}</h2>
              <div className="mt-3 space-y-3">
                {list.map((c) => (
                  <Link key={c.id} href={`/community/challenges/${c.id}`} className="flex items-center gap-4 rounded-[18px] border border-line bg-surface p-4 hover:border-line-strong">
                    <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-2xl ${c.state === "live" ? "bg-[#c9a13b]" : "bg-paper-2"}`}>
                      <TrophyIcon size={24} color={c.state === "live" ? "#fff" : "#a8842a"} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[16.5px] font-semibold text-ink">{c.title}</span>
                      <span className="block text-[13.5px] text-muted">
                        {c.state === "ended"
                          ? c.winners[0]
                            ? `Won by @${c.winners[0].author.handle}`
                            : "Ended"
                          : timeLeft(c)}{" "}
                        · {c.entries} {c.entries === 1 ? "entry" : "entries"} · {c.prizes[0]} credits for 1st
                      </span>
                    </span>
                    <span aria-hidden="true" className="text-[20px] text-muted">›</span>
                  </Link>
                ))}
              </div>
            </div>
          ) : null,
        )}
      </div>
    </section>
  );
}
