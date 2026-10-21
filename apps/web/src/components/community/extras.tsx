"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { MusicPicker } from "@/components/community/Music";
import { ThumbIcon } from "@/components/community/parts";
import { ApiError } from "@/lib/api/client";
import { community, type Challenge, type CommunityPost, type PostExtras } from "@/lib/api/endpoints";

export const PLACE = ["", "1st", "2nd", "3rd"];
const MEDAL = ["", "#c9a13b", "#9aa0a6", "#b07a4f"];

/** "3 days left", "5 hours left", "Starts in 2 days". */
export function timeLeft(c: Pick<Challenge, "state" | "starts_at" | "ends_at">): string {
  const target = new Date(c.state === "upcoming" ? c.starts_at : c.ends_at).getTime();
  const ms = target - Date.now();
  if (c.state === "ended") return "Ended";
  const hours = Math.max(0, Math.round(ms / 3_600_000));
  // whole days once it's more than a day and a half away ("7 days left", not "6" at 6 days 23 hours)
  const days = hours >= 36 ? Math.round(hours / 24) : Math.floor(hours / 24);
  const span = days >= 1 ? `${days} ${days === 1 ? "day" : "days"}` : hours >= 1 ? `${hours} ${hours === 1 ? "hour" : "hours"}` : "less than an hour";
  return c.state === "upcoming" ? `Starts in ${span}` : `${span} left`;
}

export function TrophyIcon({ size = 18, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 4h8v5a4 4 0 0 1-8 0V4z" />
      <path d="M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8.5 20h7M10 17h4v3h-4z" />
    </svg>
  );
}

export function Medal({ place, size = 22 }: { place: number; size?: number }) {
  return (
    <span
      className="grid shrink-0 place-items-center rounded-full font-bold text-white"
      style={{ width: size, height: size, background: MEDAL[place] ?? MEDAL[3], fontSize: size * 0.48 }}
      aria-label={`${PLACE[place]} place`}
    >
      {place}
    </span>
  );
}

/** The challenge running now (if any). */
export function useLiveChallenge() {
  const q = useQuery({ queryKey: ["community", "challenges"], queryFn: community.challenges });
  return { live: q.data?.live[0] ?? null, data: q.data, isLoading: q.isLoading };
}

/** Under the caption when posting: ask "Buy or skip?", and enter this week's challenge. */
export function PostOptions({ value, onChange }: { value: PostExtras; onChange: (v: PostExtras) => void }) {
  const { live } = useLiveChallenge();
  const canEnter = live && !live.my_entry_post_id;
  return (
    <div className="mt-4 space-y-2">
      <MusicPicker value={value.music_track_id} onChange={(id) => onChange({ ...value, music_track_id: id })} />
      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 hover:border-line-strong">
        <input
          type="checkbox"
          checked={!!value.poll}
          onChange={(e) => onChange({ ...value, poll: e.target.checked })}
          className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--color-sage)]"
        />
        <span>
          <span className="block text-[15px] font-semibold text-ink">Ask the community: Buy it or skip it?</span>
          <span className="block text-[13.5px] text-muted">Members vote with one tap, and you see what they think.</span>
        </span>
      </label>
      {canEnter && (
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-[#c9a13b]/50 bg-[#c9a13b]/[0.07] p-3 hover:border-[#c9a13b]">
          <input
            type="checkbox"
            checked={value.challenge_id === live.id}
            onChange={(e) => onChange({ ...value, challenge_id: e.target.checked ? live.id : null })}
            className="mt-0.5 h-5 w-5 shrink-0 accent-[#c9a13b]"
          />
          <span>
            <span className="flex items-center gap-1.5 text-[15px] font-semibold text-ink">
              <TrophyIcon size={17} color="#a8842a" /> Enter the “{live.title}” challenge
            </span>
            <span className="block text-[13.5px] text-muted">
              {timeLeft(live)} · the most liked looks win {live.prizes.filter(Boolean).join(" / ")} free credits
            </span>
          </span>
        </label>
      )}
    </div>
  );
}

/** "Buy it or skip it?" under a post that asks. */
export function PollBox({ post, onChange }: { post: CommunityPost; onChange: (p: Partial<CommunityPost>) => void }) {
  const [error, setError] = useState<string | null>(null);
  const buy = post.poll_buy ?? 0;
  const skip = post.poll_skip ?? 0;
  const total = buy + skip;
  const mine = post.my_vote ?? null;
  const vote = useMutation({
    mutationFn: (choice: "buy" | "skip") => community.vote(post.id, choice),
    onMutate: (choice) => {
      setError(null);
      const was = mine;
      onChange({
        my_vote: choice,
        poll_buy: buy + (choice === "buy" ? 1 : 0) - (was === "buy" ? 1 : 0),
        poll_skip: skip + (choice === "skip" ? 1 : 0) - (was === "skip" ? 1 : 0),
      });
    },
    onSuccess: (res) => onChange(res),
    onError: (err) => {
      onChange({ my_vote: mine, poll_buy: buy, poll_skip: skip });
      setError(err instanceof ApiError ? err.detail : "Couldn't save your vote.");
    },
  });
  const showResults = post.is_mine || !!mine;
  const pct = (n: number) => (total ? Math.round((n * 100) / total) : 0);

  return (
    <div className="mt-3 rounded-2xl border border-line bg-paper-2/60 p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[15px] font-semibold text-ink">{post.is_mine ? "You asked: Buy it or skip it?" : "Buy it or skip it?"}</p>
        <span className="text-[13px] text-muted">
          {total} {total === 1 ? "vote" : "votes"}
        </span>
      </div>
      {!showResults ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => vote.mutate("buy")}
            disabled={vote.isPending}
            className="tu-press flex min-h-[48px] items-center justify-center gap-2 rounded-xl bg-sage text-[15.5px] font-semibold text-white hover:bg-sage-deep"
          >
            <ThumbIcon size={19} /> Buy it
          </button>
          <button
            type="button"
            onClick={() => vote.mutate("skip")}
            disabled={vote.isPending}
            className="tu-press flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-line-strong bg-surface text-[15.5px] font-semibold text-ink hover:border-ink/40"
          >
            <span className="rotate-180">
              <ThumbIcon size={19} />
            </span>
            Skip it
          </button>
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          {(
            [
              ["buy", "Buy it", buy, "bg-sage"],
              ["skip", "Skip it", skip, "bg-ink/25"],
            ] as const
          ).map(([choice, label, n, color]) => (
            <button
              key={choice}
              type="button"
              disabled={post.is_mine || vote.isPending || mine === choice}
              onClick={() => vote.mutate(choice)}
              title={post.is_mine || mine === choice ? undefined : `Change my vote to ${label}`}
              className="relative block w-full overflow-hidden rounded-xl border border-line bg-surface text-left disabled:cursor-default"
            >
              <span className={`absolute inset-y-0 left-0 ${color} opacity-30 transition-[width] duration-500`} style={{ width: `${pct(n)}%` }} />
              <span className="relative flex min-h-[44px] items-center justify-between px-3.5 text-[15px]">
                <span className="font-semibold text-ink">
                  {label}
                  {mine === choice && <span className="ml-2 text-[12.5px] font-semibold text-ink-soft">✓ your vote</span>}
                </span>
                <span className="font-semibold tabular-nums text-ink">{pct(n)}%</span>
              </span>
            </button>
          ))}
          {post.is_mine && total === 0 && <p className="text-[13px] text-muted">No votes yet. Share your look to get more votes.</p>}
          {!post.is_mine && <p className="text-[12.5px] text-muted">Tap the other answer to change your vote.</p>}
        </div>
      )}
      {error && <p className="mt-2 text-[13.5px] text-[#a4553f]">{error}</p>}
    </div>
  );
}

/** The challenge chip on an entry, and a medal if it won. */
export function ChallengeChip({ post }: { post: CommunityPost }) {
  if (!post.challenge) return null;
  return (
    <Link
      href={`/community/challenges/${post.challenge.id}`}
      className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-[#c9a13b]/50 bg-[#c9a13b]/[0.08] px-3 py-1 text-[13px] font-semibold text-[#8a6d1f] hover:border-[#c9a13b]"
    >
      {post.award ? <Medal place={post.award} size={18} /> : <TrophyIcon size={15} color="#a8842a" />}
      {post.award ? `${PLACE[post.award]} place · ${post.challenge.title}` : `Challenge entry · ${post.challenge.title}`}
    </Link>
  );
}

/** The banner at the top of the community: the challenge running now. */
export function ChallengeBanner({ challenge, onJoin }: { challenge: Challenge; onJoin: () => void }) {
  return (
    <section className="relative overflow-hidden rounded-[22px] border border-[#c9a13b]/40 bg-gradient-to-br from-[#c9a13b]/[0.14] via-surface to-sage-tint/30 p-5">
      <div className="flex flex-wrap items-start gap-4">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-[#c9a13b] text-white">
          <TrophyIcon size={26} color="#fff" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] font-semibold uppercase tracking-[0.12em] text-[#8a6d1f]">
            Style challenge · {timeLeft(challenge)}
          </p>
          <h2 className="mt-0.5 font-display text-[24px] leading-tight text-ink">{challenge.title}</h2>
          {challenge.description && <p className="mt-1 text-[15px] text-ink-soft">{challenge.description}</p>}
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[14px] text-ink">
            {challenge.prizes.map((p, i) =>
              p ? (
                <span key={i} className="inline-flex items-center gap-1.5">
                  <Medal place={i + 1} size={18} /> {p} credits
                </span>
              ) : null,
            )}
            <span className="text-muted">· {challenge.entries} {challenge.entries === 1 ? "entry" : "entries"}</span>
          </p>
          {challenge.sponsor && (
            <p className="mt-1.5 text-[13.5px] text-muted">
              Sponsored by{" "}
              <Link href={`/stores/${challenge.sponsor.slug}`} className="font-semibold text-ink hover:underline">
                {challenge.sponsor.name}
              </Link>
            </p>
          )}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {challenge.my_entry_post_id ? (
          <Link
            href={`/community/post/${challenge.my_entry_post_id}`}
            className="inline-flex min-h-[44px] items-center rounded-full border border-line-strong bg-surface px-5 text-[15px] font-semibold text-ink"
          >
            ✓ You&apos;re in · View my entry
          </Link>
        ) : (
          <button
            type="button"
            onClick={onJoin}
            className="tu-press inline-flex min-h-[44px] items-center rounded-full bg-[#b08a2e] px-5 text-[15px] font-semibold text-white hover:bg-[#9a7822]"
          >
            Join the challenge
          </button>
        )}
        <Link
          href={`/community/challenges/${challenge.id}`}
          className="inline-flex min-h-[44px] items-center rounded-full border border-line-strong bg-surface px-5 text-[15px] font-semibold text-ink"
        >
          See the entries →
        </Link>
      </div>
    </section>
  );
}
