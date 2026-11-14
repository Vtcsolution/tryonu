"use client";

import { useQuery } from "@tanstack/react-query";
import { Avatar, TeamBadge } from "@/components/community/parts";
import { team } from "@/lib/api/endpoints";
import { setActingAs, useActingAs } from "@/lib/actingAs";
import { useSession } from "@/lib/auth/useSession";

/** Team members only: pick whether likes, comments and replies come from your
 * own account or one of the team's profiles. Everyone sees the badge on those. */
export function ActingAsBar() {
  const { user } = useSession();
  const isTeam = !!(user?.is_team || user?.is_admin);
  const people = useQuery({ queryKey: ["team", "people"], queryFn: team.people, enabled: isTeam, staleTime: 5 * 60_000 });
  const acting = useActingAs();
  if (!isTeam || (people.data ?? []).length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[18px] border border-sage/40 bg-sage-tint/30 px-3 py-2.5 text-[14px] text-ink">
      <span className="font-semibold">Like and comment as:</span>
      {acting && <Avatar name={acting.name} handle={acting.handle} url={acting.avatar_url} size={24} />}
      <select
        value={acting?.id ?? ""}
        onChange={(e) => {
          const p = (people.data ?? []).find((x) => x.id === e.target.value);
          setActingAs(p ? { id: p.id, handle: p.handle, name: p.name, avatar_url: p.avatar_url } : null);
        }}
        aria-label="Like and comment as"
        className="min-h-[36px] rounded-full border border-line-strong bg-surface px-3 text-[14px]"
      >
        <option value="">Me ({user?.full_name || user?.email})</option>
        {(people.data ?? []).map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} (@{p.handle})
          </option>
        ))}
      </select>
      {acting && <TeamBadge />}
      <span className="text-[13px] text-muted">Only you see this bar. Team profiles always show the TryOnU team badge.</span>
    </div>
  );
}
