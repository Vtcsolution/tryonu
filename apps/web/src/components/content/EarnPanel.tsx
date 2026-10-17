"use client";

import { useQuery } from "@tanstack/react-query";
import { EarnRules } from "@/components/referrals/EarnRules";
import { ShareLook } from "@/components/try/ShareLook";
import { Button } from "@/components/ui/Button";
import { referrals as referralsApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** Signed in: your two links (friends and shops), the rules, and what you earned.
 * Otherwise: the rules and "create an account first". */
export function EarnPanel() {
  const { user, isLoading } = useSession();
  const me = useQuery({ queryKey: ["referrals", "me"], queryFn: referralsApi.me, enabled: !!user, staleTime: 60_000 });

  if (isLoading || (user && me.isLoading)) {
    return <div className="h-[220px] animate-pulse rounded-[24px] bg-paper-2" />;
  }
  if (!user) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6 md:p-8">
        <div>
          <p className="font-display text-[26px] text-ink">Get your invite links</p>
          <p className="mt-1 text-[16px] text-ink-soft">Create a free account (or sign in) to get your personal links.</p>
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
  const stats: [string, number][] = [
    ["Friends joined", d.friends_joined],
    ["Friends who tried on", d.friends_tried],
    ["Shops that bought a plan", d.stores_bought],
    ["Credits you earned", d.credits_earned],
  ];
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-[18px] border border-line bg-surface p-4">
            <p className="text-[13px] text-muted">{label}</p>
            <p className="mt-1 font-display text-[32px] leading-none text-ink">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <LinkCard
          title="Invite friends"
          text="Send this to friends and family, or post it on WhatsApp, Facebook and other social media."
          link={d.link}
          shareTitle="Invite friends to TryOnU"
          message="See yourself in any outfit before you buy it. Join me on TryOnU:"
        />
        <LinkCard
          title="Invite a shop"
          text="Know a clothing or shoe shop? Send them this. They can open a store on TryOnU and reach more customers."
          link={d.store_link}
          shareTitle="Invite a shop to TryOnU"
          message="Sell your clothes on TryOnU: customers see your products on themselves before they buy. Open your store here:"
        />
      </div>

      <div className="rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6">
        <p className="text-[18px] font-semibold text-ink">How you earn</p>
        <div className="mt-3">
          <EarnRules summary={d} />
        </div>
        <p className="mt-3 text-[14px] text-muted">Credits are added to your account automatically. You can see them in your credit history.</p>
      </div>
    </div>
  );
}

function LinkCard({ title, text, link, shareTitle, message }: { title: string; text: string; link: string; shareTitle: string; message: string }) {
  return (
    <div className="flex flex-col rounded-[24px] border border-line bg-surface p-6">
      <p className="text-[19px] font-semibold text-ink">{title}</p>
      <p className="mt-1 text-[15px] text-ink-soft">{text}</p>
      <p className="mt-3 break-all rounded-xl bg-paper-2 px-3 py-2 font-mono text-[14px] text-ink">{link}</p>
      <div className="mt-4">
        <ShareLook url={link} variant="wide" label="Share this link" title={shareTitle} message={message} earns />
      </div>
    </div>
  );
}
