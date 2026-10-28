"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminEmail, adminMessages, type ContactMessage } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText, when } from "./ui";

/** Messages from the website's Contact page: read, reply by email, mark done. */
export function MessagesTab() {
  const qc = useQueryClient();
  const [show, setShow] = useState<"open" | "all">("open");
  const [replying, setReplying] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["admin", "messages", show], queryFn: () => adminMessages.list(show) });
  const handled = useMutation({
    mutationFn: ({ id, undo }: { id: string; undo: boolean }) => adminMessages.handled(id, undo),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "messages"] }),
  });

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Messages"
        hint="Messages from the Contact page. Press Reply: it's sent from the site's address and the message is marked done."
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
              <SmallButton tone="primary" onClick={() => setReplying(replying === m.id ? null : m.id)}>
                {replying === m.id ? "Close reply" : "Reply"}
              </SmallButton>
              <SmallButton
                disabled={handled.isPending}
                onClick={() => handled.mutate({ id: m.id, undo: !!m.handled_at })}
              >
                {m.handled_at ? "Reopen" : "Mark as done"}
              </SmallButton>
            </div>
            {replying === m.id && <Reply message={m} onSent={() => setReplying(null)} />}
          </article>
        ))}
      </div>
    </div>
  );
}

/** An answer to a Contact message, sent from the site's own address; the message is then done. */
function Reply({ message, onSent }: { message: ContactMessage; onSent: () => void }) {
  const qc = useQueryClient();
  const first = message.name.split(" ")[0];
  const [text, setText] = useState(`Hi ${first},\n\n\n\nBest wishes,\nTryOnU`);
  const send = useMutation({
    mutationFn: async () => {
      await adminEmail.send({ audience: "one", to: message.email, subject: "Re: your message to TryOnU", message: text.trim() });
      if (!message.handled_at) await adminMessages.handled(message.id, false);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "messages"] });
      qc.invalidateQueries({ queryKey: ["admin", "email"] });
      onSent();
    },
  });
  return (
    <div className="mt-3 rounded-[14px] border border-line bg-paper p-3">
      <p className="text-[13.5px] text-muted">To {message.email}</p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={7}
        className="mt-2 w-full rounded-xl border border-line-strong bg-surface p-3 text-[15px] text-ink outline-none focus:border-sage"
      />
      {send.isError && <ErrorNote>{errorText(send.error)}</ErrorNote>}
      <div className="mt-2">
        <SmallButton tone="primary" disabled={send.isPending || text.trim().length < 2} onClick={() => send.mutate()}>
          {send.isPending ? "Sending…" : "Send reply"}
        </SmallButton>
      </div>
    </div>
  );
}
