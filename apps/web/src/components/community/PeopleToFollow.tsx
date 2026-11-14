"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Avatar, TeamBadge } from "@/components/community/parts";
import { community } from "@/lib/api/endpoints";

/** Members worth following, with a one-tap Follow: a row that scrolls
 * sideways in the feed (phones), or a list in the side column. */
export function PeopleToFollow({ variant = "row" }: { variant?: "row" | "list" }) {
  const people = useQuery({ queryKey: ["community", "people", "suggested"], queryFn: () => community.suggestedPeople(12), staleTime: 5 * 60_000 });
  const qc = useQueryClient();
  const [followed, setFollowed] = useState<Set<string>>(new Set());
  const follow = useMutation({
    mutationFn: (handle: string) => (followed.has(handle) ? community.unfollow(handle) : community.follow(handle)),
    onMutate: (handle) =>
      setFollowed((s) => {
        const next = new Set(s);
        if (next.has(handle)) next.delete(handle);
        else next.add(handle);
        return next;
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["community", "feed", "following"] }),
  });
  const list = people.data ?? [];
  if (list.length === 0) return null;

  const button = (handle: string) => {
    const on = followed.has(handle);
    return (
      <button
        type="button"
        onClick={() => follow.mutate(handle)}
        className={`tu-press min-h-[36px] rounded-full px-4 text-[14px] font-semibold ${
          on ? "border border-line-strong text-ink" : "bg-sage text-white hover:bg-sage-deep"
        }`}
      >
        {on ? "Following" : "Follow"}
      </button>
    );
  };

  if (variant === "list") {
    return (
      <div className="rounded-[20px] border border-line bg-surface p-5">
        <p className="text-[16px] font-semibold text-ink">People to follow</p>
        <ul className="mt-3 space-y-3">
          {list.slice(0, 6).map((p) => (
            <li key={p.handle} className="flex items-center gap-3">
              <Link href={`/u/${p.handle}`} className="flex min-w-0 flex-1 items-center gap-3">
                <Avatar name={p.name} handle={p.handle} url={p.avatar_url} size={40} />
                <span className="min-w-0">
                  <span className="flex min-w-0 items-center gap-1.5">
                    <span className="truncate text-[15px] font-semibold text-ink">{p.name || p.handle}</span>
                    {p.team && <TeamBadge />}
                  </span>
                  <span className="block truncate text-[13px] text-muted">
                    {p.follows_me ? "Follows you" : `${p.followers} followers · ${p.posts} posts`}
                  </span>
                </span>
              </Link>
              {button(p.handle)}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <section aria-label="People to follow" className="rounded-[22px] border border-line bg-surface p-4">
      <p className="text-[16px] font-semibold text-ink">People to follow</p>
      <ul className="-mx-1 mt-3 flex snap-x gap-3 overflow-x-auto px-1 pb-1">
        {list.map((p) => (
          <li key={p.handle} className="flex w-[150px] shrink-0 snap-start flex-col items-center rounded-[18px] border border-line p-3 text-center">
            <Link href={`/u/${p.handle}`} className="flex flex-col items-center">
              <Avatar name={p.name} handle={p.handle} url={p.avatar_url} size={56} />
              <span className="mt-2 block w-full truncate text-[14.5px] font-semibold text-ink">{p.name || p.handle}</span>
              {p.team && <TeamBadge className="mt-1" />}
              <span className="block w-full truncate text-[12.5px] text-muted">
                {p.follows_me ? "Follows you" : `${p.followers} followers`}
              </span>
            </Link>
            <div className="mt-2.5">{button(p.handle)}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
