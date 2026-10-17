"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { resolveMediaUrl } from "@/lib/api/client";
import { adminCommunity } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText, when } from "./ui";

/** Reported community posts and comments: hide them, block the member, or dismiss. */
export function CommunityTab() {
  const qc = useQueryClient();
  const [show, setShow] = useState<"open" | "all">("open");
  const list = useQuery({ queryKey: ["admin", "community", show], queryFn: () => adminCommunity.reports(show) });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "hide" | "dismiss" | "ban" }) => adminCommunity.resolve(id, action),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "community"] }),
  });
  return (
    <div className="space-y-5">
      <SectionHeader
        title="Community reports"
        hint="Posts and comments members reported. Hide: it disappears. Block member: they can't post or comment, and their posts and comments disappear. Dismiss: nothing wrong."
      >
        <div className="flex gap-2">
          <SmallButton tone={show === "open" ? "primary" : undefined} onClick={() => setShow("open")}>Open</SmallButton>
          <SmallButton tone={show === "all" ? "primary" : undefined} onClick={() => setShow("all")}>All</SmallButton>
        </div>
      </SectionHeader>
      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      {list.data && list.data.length === 0 && (
        <p className="rounded-[16px] border border-dashed border-line p-8 text-center text-[15px] text-muted">
          {show === "open" ? "Nothing to review. 🎉" : "No reports yet."}
        </p>
      )}
      <div className="space-y-3">
        {list.data?.map((r) => (
          <article key={r.id} className="flex flex-wrap gap-4 rounded-[18px] border border-line bg-surface p-4">
            {r.image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={resolveMediaUrl(r.image_url)} alt="" className="h-32 w-24 shrink-0 rounded-xl bg-paper-2 object-cover object-top" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{r.kind === "post" ? "Post" : "Comment"}</Badge>
                {r.hidden ? <Badge tone="bad">Hidden</Badge> : r.resolved_at ? <Badge tone="good">Done</Badge> : <Badge tone="warn">Open</Badge>}
                <span className="text-[13px] text-faint">{when(r.created_at)}</span>
              </div>
              <p className="mt-2 text-[14.5px] text-ink">
                By <b>@{r.author_handle ?? "?"}</b> <span className="text-muted">({r.author_email})</span>
              </p>
              {r.text && <p className="mt-1 whitespace-pre-wrap rounded-lg bg-paper-2 px-3 py-2 text-[14.5px] text-ink-soft">{r.text}</p>}
              <p className="mt-2 text-[13.5px] text-muted">
                Reported by {r.reporter_email}: “{r.reason}”
              </p>
              {!r.resolved_at && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <SmallButton tone="danger" disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "hide" })}>Hide</SmallButton>
                  <SmallButton tone="danger" disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "ban" })}>Hide + block member</SmallButton>
                  <SmallButton disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "dismiss" })}>Dismiss</SmallButton>
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
