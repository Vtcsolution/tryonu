"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminMessages } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText, when } from "./ui";

/** Messages from the website's Contact page: read, reply by email, mark done. */
export function MessagesTab() {
  const qc = useQueryClient();
  const [show, setShow] = useState<"open" | "all">("open");
  const list = useQuery({ queryKey: ["admin", "messages", show], queryFn: () => adminMessages.list(show) });
  const handled = useMutation({
    mutationFn: ({ id, undo }: { id: string; undo: boolean }) => adminMessages.handled(id, undo),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "messages"] }),
  });

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Messages"
        hint="Messages from the Contact page. Reply by email, then press Done."
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
          {show === "open" ? "No open messages." : "No messages yet."}
        </p>
      )}
      <div className="space-y-3">
        {list.data?.map((m) => (
          <article key={m.id} className="rounded-[18px] border border-line bg-surface p-5">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[16px] font-semibold text-ink">{m.name}</p>
              <a href={`mailto:${m.email}`} className="text-[14px] text-sage-deep hover:underline">{m.email}</a>
              <Badge>{m.topic_label}</Badge>
              {m.handled_at ? <Badge tone="good">Done</Badge> : <Badge tone="warn">Open</Badge>}
              <span className="ml-auto text-[13px] text-faint">{when(m.created_at)}</span>
            </div>
            <p className="mt-3 whitespace-pre-wrap text-[15px] leading-relaxed text-ink-soft">{m.message}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <a
                href={`mailto:${m.email}?subject=${encodeURIComponent(`Re: your message to TryOnU`)}`}
                className="inline-flex min-h-[36px] items-center rounded-full bg-ink px-4 text-[13.5px] font-semibold text-surface"
              >
                Reply by email
              </a>
              <SmallButton
                disabled={handled.isPending}
                onClick={() => handled.mutate({ id: m.id, undo: !!m.handled_at })}
              >
                {m.handled_at ? "Reopen" : "Mark as done"}
              </SmallButton>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
