"use client";

import { useQuery } from "@tanstack/react-query";
import { ShareLook } from "@/components/try/ShareLook";
import { Button } from "@/components/ui/Button";
import { referrals as referralsApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** Signed in: your invite link and what it earned. Otherwise: create an account first. */
export function EarnPanel() {
  const { user, isLoading } = useSession();
  const me = useQuery({ queryKey: ["referrals", "me"], queryFn: referralsApi.me, enabled: !!user, staleTime: 60_000 });

  if (isLoading || (user && me.isLoading)) {
    return <div className="h-[168px] animate-pulse rounded-[24px] bg-paper-2" />;
  }
  if (!user) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6 md:p-8">
        <div>
          <p className="font-display text-[26px] text-ink">Get your invite link</p>
          <p className="mt-1 text-[16px] text-ink-soft">Create a free account (or sign in) to get your personal link.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button href="/sign-up?next=/earn" size="lg">Create account</Button>
          <Button href="/sign-in?next=/earn" size="lg" variant="outline">Sign in</Button>
        </div>
      </div>
    );
  }
  const d = me.data;
  if (!d) return null;
  return (
    <div className="grid gap-6 rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:p-8">
      <div className="min-w-0">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Your invite link</p>
        <p className="mt-2 break-all font-mono text-[15px] text-ink">{d.link}</p>
        <p className="mt-3 text-[16px] text-ink-soft">
          {d.reward_credits > 0 ? (
            <>
              You earn <b className="text-ink">{d.reward_credits} credits</b> for each friend who joins and buys credits.
            </>
          ) : (
            "Rewards are paused right now, but you can still share your link."
          )}
        </p>
        <div className="mt-4 grid max-w-md grid-cols-3 gap-3">
          {[
            ["Friends joined", d.friends_joined],
            ["Bought credits", d.friends_bought],
            ["Credits earned", d.credits_earned],
          ].map(([label, value]) => (
            <div key={label} className="rounded-[14px] border border-line bg-surface p-3">
              <p className="text-[12px] uppercase tracking-[0.06em] text-faint">{label}</p>
              <p className="mt-0.5 font-display text-[24px] text-ink">{value}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="w-full md:w-[280px]">
        <ShareLook
          url={d.link}
          variant="wide"
          label="Share my invite link"
          title="Invite friends to TryOnU"
          message="See yourself in any outfit before you buy it. Join me on TryOnU:"
          earns
        />
      </div>
    </div>
  );
}
