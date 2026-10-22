"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminAnnouncements } from "@/lib/api/endpoints";
import { ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText, inputClass, when } from "./ui";

// ready-made messages: one tap fills the box
const IDEAS: { text: string; url: string }[] = [
  { text: "Eid Mubarak! Try your Eid outfit on your own photo before you buy.", url: "/try" },
  { text: "New style challenge this week: post your look and win free credits!", url: "/community/challenges" },
  { text: "Find any outfit from a photo: try Find by photo.", url: "/find-look" },
  { text: "Invite a friend and earn free credits.", url: "/earn" },
];

const KEY = ["admin", "announcements"];

/** One message to every member: the bell, and their phone when they turned notifications on. */
export function AnnouncementsAdmin() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: KEY, queryFn: adminAnnouncements.list });
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const send = useMutation({
    mutationFn: () => adminAnnouncements.send({ text: text.trim(), url: url.trim() || undefined }),
    onSuccess: () => {
      setText("");
      setUrl("");
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
  const members = list.data?.members ?? 0;

  return (
    <div>
      <SectionHeader
        title="Announcements"
        hint="One short message to every member, in the bell and on their phone."
      />
      <div className="rounded-[16px] border border-line bg-surface p-4">
        <div className="flex flex-wrap gap-2">
          {IDEAS.map((i) => (
            <SmallButton
              key={i.text}
              onClick={() => {
                setText(i.text);
                setUrl(i.url);
              }}
            >
              {i.text.length > 34 ? `${i.text.slice(0, 33)}…` : i.text}
            </SmallButton>
          ))}
        </div>
        <label className="mt-4 block text-[13.5px] font-medium text-ink-soft">
          Message ({280 - text.length} letters left)
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, 280))}
            rows={3}
            placeholder="e.g. Eid sale: 20% more credits this week!"
            className={`${inputClass} mt-1 h-auto w-full py-2`}
          />
        </label>
        <label className="mt-3 block text-[13.5px] font-medium text-ink-soft">
          Opens this page when tapped (optional)
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="/credits" className={`${inputClass} mt-1 w-full`} />
        </label>
        {send.isError && (
          <div className="mt-2">
            <ErrorNote>{errorText(send.error)}</ErrorNote>
          </div>
        )}
        {send.isSuccess && <p className="mt-2 text-[14px] text-sage-deep">Sent to {send.data.sent_to.toLocaleString()} members ✓</p>}
        <div className="mt-3">
          <SmallButton
            tone="primary"
            disabled={send.isPending || text.trim().length < 3}
            onClick={() => window.confirm(`Send this to all ${members.toLocaleString()} members now?\n\n“${text.trim()}”`) && send.mutate()}
          >
            {send.isPending ? "Sending…" : `Send to all ${members.toLocaleString()} members`}
          </SmallButton>
        </div>
      </div>

      <p className="mt-6 text-[13px] font-semibold uppercase tracking-[0.12em] text-faint">Sent before</p>
      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      {list.data && list.data.items.length === 0 && <p className="mt-2 text-[14px] text-muted">Nothing sent yet.</p>}
      <div className="mt-2 space-y-2">
        {list.data?.items.map((a) => (
          <div key={a.id} className="rounded-[14px] border border-line bg-surface p-3">
            <p className="text-[15px] text-ink">{a.text}</p>
            <p className="mt-1 text-[13px] text-muted">
              {when(a.created_at)} · {a.sent_to.toLocaleString()} members{a.url ? ` · opens ${a.url}` : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
