"use client";

import { useQuery } from "@tanstack/react-query";
import { adminReferrals } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, StatTile, Table, TableSkeleton, errorText, when } from "./ui";

/** Share and earn: who invited whom, what the friend did, and the credits paid out. */
export function ReferralsTab() {
  const q = useQuery({ queryKey: ["admin", "referrals"], queryFn: adminReferrals.list });
  const d = q.data;
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="People who joined from a link" value={d?.invites ?? "…"} />
        <StatTile label="Of them, did a try-on" value={d?.tried_on ?? "…"} />
        <StatTile label="Shops that bought a plan" value={d?.stores_bought ?? "…"} />
        <StatTile label="Credits paid as rewards" value={d?.credits_paid ?? "…"} />
      </div>
      <div>
        <SectionHeader
          title="Invites"
          hint="Friends who joined from someone's link. The sharer earns credits on the friend's first try-on."
        />
        {q.isError && <ErrorNote>{errorText(q.error)}</ErrorNote>}
        {q.isLoading ? (
          <TableSkeleton />
        ) : (
          <Table
            columns={["Shared by", "Friend who joined", "From", "Joined", "First try-on", "Shop plan", "Credits earned"]}
            empty="Nobody has joined from a shared link yet."
            rows={(d?.rows ?? []).map((r) => [
              <span key="a" className="text-ink">{r.inviter_email}</span>,
              r.friend_email,
              r.source,
              when(r.joined_at),
              r.tried_on_at ? <Badge key="t" tone="good">{when(r.tried_on_at)}</Badge> : <span key="t" className="text-faint">not yet</span>,
              r.store_plan ? <Badge key="s" tone="good">{r.store_plan}</Badge> : <span key="s" className="text-faint">—</span>,
              <b key="c" className="text-ink">{r.credits_earned}</b>,
            ])}
          />
        )}
      </div>
    </div>
  );
}
