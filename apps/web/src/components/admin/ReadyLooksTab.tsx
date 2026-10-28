"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { LookCard } from "@/components/looks/TeamPanel";
import { team } from "@/lib/api/endpoints";
import { ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText } from "./ui";

type Show = "all" | "on" | "draft";
type Who = "all" | "women" | "men" | "kids";

/** Every Ready look, drafts included, whoever made it: visit, edit, publish or hide, delete. */
export function ReadyLooksTab() {
  // the same list (and query key) as the team panel, so edits show in both
  const looks = useQuery({ queryKey: ["team", "looks"], queryFn: team.looks });
  const [show, setShow] = useState<Show>("all");
  const [who, setWho] = useState<Who>("all");
  const all = looks.data ?? [];
  const list = all.filter(
    (l) =>
      (show === "on" ? l.is_published : show === "draft" ? !l.is_published : true) && (who === "all" || l.audience === who),
  );

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Ready looks"
        hint="Every Ready look, from the team and from members' community posts. Press Edit to publish, hide, rename or delete."
      >
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["all", `All (${all.length})`],
              ["on", `On the site (${all.filter((l) => l.is_published).length})`],
              ["draft", `Drafts (${all.filter((l) => !l.is_published).length})`],
            ] as [Show, string][]
          ).map(([v, label]) => (
            <SmallButton key={v} tone={show === v ? "primary" : undefined} onClick={() => setShow(v)}>
              {label}
            </SmallButton>
          ))}
        </div>
      </SectionHeader>
      <div className="flex flex-wrap gap-2">
        {(["all", "women", "men", "kids"] as Who[]).map((v) => (
          <SmallButton key={v} tone={who === v ? "primary" : undefined} onClick={() => setWho(v)}>
            {v === "all" ? "Everyone" : v[0].toUpperCase() + v.slice(1)}
          </SmallButton>
        ))}
      </div>
      {looks.isError && <ErrorNote>{errorText(looks.error)}</ErrorNote>}
      {looks.isLoading && <TableSkeleton />}
      {!looks.isLoading && list.length === 0 && (
        <p className="rounded-[16px] border border-dashed border-line p-8 text-center text-[15px] text-muted">No looks here yet.</p>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {list.map((look) => (
          <LookCard key={look.id} look={look} />
        ))}
      </div>
    </div>
  );
}
