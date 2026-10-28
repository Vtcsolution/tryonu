"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { mediaThumb } from "@/lib/api/client";
import { adminOutfits, team, type AdminOutfit } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SimplePager, SmallButton, TableSkeleton, errorText, inputClass, when } from "./ui";

type Who = "all" | "members" | "team";
const PAGE = 24;

/** Every finished try-on picture, shoppers' and the team's, newest first. */
export function OutfitsTab() {
  const [who, setWho] = useState<Who>("all");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const list = useQuery({
    queryKey: ["admin", "outfits", who, search, offset],
    queryFn: () => adminOutfits.list({ who, q: search || undefined, offset, limit: PAGE }),
  });
  const d = list.data;

  return (
    <div className="space-y-5">
      <SectionHeader title="All outfits" hint="Every finished try-on: members' and the team's. Open it, or add it to Ready looks.">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(q.trim());
            setOffset(0);
          }}
        >
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email or name" className={inputClass} />
          <SmallButton type="submit">Search</SmallButton>
        </form>
      </SectionHeader>
      <div className="flex flex-wrap gap-2">
        {(
          [
            ["all", `Everyone (${d ? d.members + d.team : "…"})`],
            ["members", `Members (${d?.members ?? "…"})`],
            ["team", `Team (${d?.team ?? "…"})`],
          ] as [Who, string][]
        ).map(([v, label]) => (
          <SmallButton
            key={v}
            tone={who === v ? "primary" : undefined}
            onClick={() => {
              setWho(v);
              setOffset(0);
            }}
          >
            {label}
          </SmallButton>
        ))}
      </div>
      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      {d && d.items.length === 0 && (
        <p className="rounded-[16px] border border-dashed border-line p-8 text-center text-[15px] text-muted">No outfits here yet.</p>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        {d?.items.map((o) => <OutfitCard key={o.id} outfit={o} />)}
      </div>
      {d && d.total > PAGE && <SimplePager offset={offset} count={d.items.length} onChange={setOffset} />}
    </div>
  );
}

function OutfitCard({ outfit: o }: { outfit: AdminOutfit }) {
  const qc = useQueryClient();
  const add = useMutation({
    mutationFn: async () => {
      const s = await team.suggest(o.id);
      return team.publish({ tryon_job_id: o.id, title: s.title, audience: s.audience, season: s.season, publish: false });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "outfits"] });
      qc.invalidateQueries({ queryKey: ["team", "looks"] });
    },
  });
  const lookId = o.ready_look_id ?? add.data?.id ?? null;
  return (
    <article className="overflow-hidden rounded-[16px] border border-line bg-surface">
      <a href={o.image_url} target="_blank" rel="noopener noreferrer" className="relative block bg-paper-2" title="Open the full picture">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={mediaThumb(o.image_url, 400)} alt={o.what} loading="lazy" className="aspect-[3/4] w-full object-cover object-top" />
        {o.is_team && <span className="absolute left-2 top-2 rounded-full bg-sage px-2.5 py-0.5 text-[12px] font-semibold text-white">Team</span>}
      </a>
      <div className="space-y-1.5 p-3">
        <p className="truncate text-[14px] font-semibold text-ink" title={o.user_email ?? ""}>
          {o.user_name || o.user_email || "—"}
        </p>
        <p className="line-clamp-1 text-[13px] text-muted" title={o.what}>{o.what}</p>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[12px] text-faint">{when(o.created_at)}</span>
          {o.community_posts > 0 && <Badge>Community</Badge>}
          {lookId && <Badge tone="good">Ready look</Badge>}
        </div>
        {add.isError && <p className="text-[12.5px] text-[#a4553f]">{errorText(add.error)}</p>}
        <div className="pt-1">
          {lookId ? (
            <Link href={`/looks/${lookId}`} target="_blank" className="text-[13.5px] font-semibold text-sage-deep hover:underline">
              Visit the look ↗
            </Link>
          ) : (
            <SmallButton disabled={add.isPending} onClick={() => add.mutate()}>
              {add.isPending ? "Adding…" : "Add to Ready looks (draft)"}
            </SmallButton>
          )}
        </div>
      </div>
    </article>
  );
}
