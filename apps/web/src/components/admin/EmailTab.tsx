"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminEmail, type AdminEmailAudience } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SmallButton, errorText, when } from "./ui";

const KEY = ["admin", "email"];
const field =
  "w-full rounded-xl border border-line-strong bg-paper px-3.5 py-2.5 text-[15px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25";

// a ready text for the smart email, one tap away
const READY_SUBJECT = "See yourself in this week's top looks";
const READY_MESSAGE =
  "Hi {name},\n\nThese are the looks everyone is trying on TryOnU this week. Pick one, upload one photo, and see the whole outfit on you in about a minute, before you buy a single piece.\n\nEvery piece is a real product from a real shop, so when you love your look, you can buy it right away.";

const WHO: Record<AdminEmailAudience, string> = {
  one: "One person",
  me: "Test to me",
  members: "All members",
  stores: "All shop owners",
  team: "The team",
};

/** Write an email from the site's own address: to one person, every member
 * who gets emails, every shop owner or the team. */
export function EmailTab() {
  const qc = useQueryClient();
  const counts = useQuery({ queryKey: [...KEY, "audiences"], queryFn: adminEmail.audiences });
  const history = useQuery({
    queryKey: [...KEY, "history"],
    queryFn: adminEmail.history,
    // a group email goes out slowly from its queue: follow it while it does
    refetchInterval: (q) => (q.state.data?.some((e) => e.status !== "done") ? 10000 : false),
  });
  const [audience, setAudience] = useState<AdminEmailAudience>("one");
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  // smart: the admin only writes; matching looks and links are added by the site
  const [template, setTemplate] = useState<"looks" | null>("looks");
  const preview = useMutation({
    mutationFn: () => adminEmail.preview({ subject: subject.trim(), message: message.trim(), template }),
  });
  const send = useMutation({
    mutationFn: (who: AdminEmailAudience) =>
      adminEmail.send({ audience: who, to: who === "one" ? to.trim() : undefined, subject: subject.trim(), message: message.trim(), template }),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: [...KEY, "history"] });
      qc.invalidateQueries({ queryKey: [...KEY, "audiences"] });
      if (row.audience !== "me") {
        setSubject("");
        setMessage("");
      }
    },
  });

  const c = counts.data;
  const size: Record<AdminEmailAudience, number> = { one: 1, me: 1, members: c?.members ?? 0, stores: c?.stores ?? 0, team: c?.team ?? 0 };
  const ready = subject.trim().length >= 2 && message.trim().length >= 2 && (audience !== "one" || /\S+@\S+\.\S+/.test(to));
  const group = audience === "members" || audience === "stores" || audience === "team";

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Send email"
        hint={`From ${c?.from_address ?? "the site's address"}. Replies go to your help inbox.`}
      />
      {c && !c.sending_ready && (
        <ErrorNote>
          Email isn&apos;t set up yet, so nothing can be sent. Fill in Settings &amp; keys → Email (SMTP host, username,
          password and From address), press Save, then come back.
        </ErrorNote>
      )}

      <div className="rounded-[18px] border border-line bg-surface p-5">
        <p className="text-[14px] font-semibold text-ink">Kind of email</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <SmallButton tone={template === "looks" ? "primary" : undefined} onClick={() => setTemplate("looks")}>
            Smart email: looks and links added for you
          </SmallButton>
          <SmallButton tone={template === null ? "primary" : undefined} onClick={() => setTemplate(null)}>
            Plain message
          </SmallButton>
        </div>
        <p className="mt-2 text-[13.5px] text-muted">
          {template === "looks"
            ? "Just write your words. The site adds up to 10 Ready looks that match them (write \"men\", \"winter\", \"bridal\"… to choose; otherwise the trending ones) with pictures and \"Try it on you\" buttons, then \"How it works\" and a big button. Words like Ready looks, try on, community or pricing become links by themselves."
            : "Just your words, with the TryOnU heading. Words like Ready looks, try on, community or pricing become links by themselves."}
        </p>

        <p className="mt-5 text-[14px] font-semibold text-ink">Send to</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {(["one", "members", "stores", "team"] as AdminEmailAudience[]).map((a) => (
            <SmallButton key={a} tone={audience === a ? "primary" : undefined} onClick={() => setAudience(a)}>
              {WHO[a]}
              {a !== "one" && c ? ` (${size[a]})` : ""}
            </SmallButton>
          ))}
        </div>
        {audience === "members" && (
          <p className="mt-2 text-[13.5px] text-muted">
            Only members who keep emails on. Each email has a link to stop them.
          </p>
        )}
        {group && c && (
          <p className="mt-2 text-[13.5px] text-muted">
            It goes out slowly by itself: about {c.per_hour} an hour and at most {c.per_day} a day ({c.sent_today} sent
            today), so Hostinger never blocks the mailbox. A big list simply continues the next day.
            {size[audience] > c.max_per_send ? ` One email can go to at most ${c.max_per_send} people.` : ""}
          </p>
        )}

        {audience === "one" && (
          <label className="mt-4 block text-[14px] font-medium text-ink-soft">
            Email address
            <input type="email" value={to} onChange={(e) => setTo(e.target.value)} placeholder="name@example.com" className={`${field} mt-1`} />
          </label>
        )}
        <label className="mt-4 block text-[14px] font-medium text-ink-soft">
          Subject
          <input value={subject} onChange={(e) => setSubject(e.target.value.slice(0, 200))} placeholder="e.g. New winter looks are here" className={`${field} mt-1`} />
        </label>
        <label className="mt-4 block text-[14px] font-medium text-ink-soft">
          Message
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={8}
            placeholder={"Hi {name},\n\nWrite your message here. No links needed: the looks and links are added for you."}
            className={`${field} mt-1`}
          />
        </label>
        {!message.trim() && (
          <button
            type="button"
            onClick={() => {
              if (!subject.trim()) setSubject(READY_SUBJECT);
              setMessage(READY_MESSAGE);
            }}
            className="mt-1 text-[13.5px] font-semibold text-sage-deep hover:underline"
          >
            Use a ready text
          </button>
        )}
        <p className="mt-1 text-[13px] text-muted">
          <b>{"{name}"}</b> becomes each person&apos;s first name. The TryOnU name and a short footer are added for you.
        </p>

        {send.isError && <div className="mt-3"><ErrorNote>{errorText(send.error)}</ErrorNote></div>}
        {send.isSuccess && (
          <p className="mt-3 rounded-xl bg-sage-tint/60 px-4 py-2.5 text-[14.5px] text-ink">
            {send.data.audience === "me"
              ? "Test sent to your own email. Check your inbox (and spam)."
              : send.data.status === "done"
                ? `Sent to ${send.data.to_address}.`
                : `Queued for ${send.data.total} people. It goes out slowly by itself; watch it below.`}
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!ready || send.isPending || (group && size[audience] === 0)}
            onClick={() => {
              if (group && !window.confirm(`Send this email to ${size[audience]} people?`)) return;
              send.mutate(audience);
            }}
            className="tu-press min-h-[42px] rounded-full bg-sage px-5 text-[15px] font-semibold text-white disabled:opacity-50"
          >
            {send.isPending ? "Sending…" : audience === "one" ? "Send" : `Send to ${size[audience]} people`}
          </button>
          <button
            type="button"
            disabled={preview.isPending}
            onClick={() => preview.mutate()}
            className="min-h-[42px] rounded-full border border-line-strong px-5 text-[15px] font-semibold text-ink disabled:opacity-50"
          >
            {preview.isPending ? "Making preview…" : "Preview"}
          </button>
          <button
            type="button"
            disabled={subject.trim().length < 2 || message.trim().length < 2 || send.isPending}
            onClick={() => send.mutate("me")}
            className="min-h-[42px] rounded-full border border-line-strong px-5 text-[15px] font-semibold text-ink disabled:opacity-50"
          >
            Send a test to me
          </button>
        </div>
      </div>

      {preview.isError && <ErrorNote>{errorText(preview.error)}</ErrorNote>}
      {preview.data && (
        <div className="rounded-[18px] border border-line bg-surface p-3">
          <div className="flex items-center justify-between px-2 pb-2">
            <p className="text-[14px] font-semibold text-ink">Preview: what people will see</p>
            <SmallButton onClick={() => preview.reset()}>Close</SmallButton>
          </div>
          <iframe
            title="Email preview"
            srcDoc={preview.data.html}
            sandbox=""
            className="h-[720px] w-full rounded-xl border border-line bg-white"
          />
        </div>
      )}

      <div>
        <p className="text-[14px] font-semibold text-ink">Sent emails</p>
        {history.isError && <ErrorNote>{errorText(history.error)}</ErrorNote>}
        {history.data && history.data.length === 0 && <p className="mt-2 text-[14.5px] text-muted">Nothing sent yet.</p>}
        <div className="mt-2 space-y-2">
          {history.data?.map((e) => (
            <div key={e.id} className="flex flex-wrap items-center gap-2 rounded-[14px] border border-line bg-surface px-4 py-3">
              <p className="min-w-0 flex-1 truncate text-[15px] font-medium text-ink">{e.subject}</p>
              <span className="text-[13.5px] text-muted">{e.to_address ?? WHO[e.audience]}</span>
              {e.status === "queued" ? (
                <Badge tone="warn">Waiting to start · {e.total}</Badge>
              ) : e.status === "sending" ? (
                <Badge tone="warn">Sending {e.sent + e.failed}/{e.total}</Badge>
              ) : e.status === "paused" ? (
                <span title={e.last_error ?? ""}>
                  <Badge tone="warn">
                    Paused {e.sent + e.failed}/{e.total}
                    {e.paused_until ? ` · goes on at ${new Date(e.paused_until).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}
                  </Badge>
                </span>
              ) : e.failed ? (
                <Badge tone="bad">{e.sent} sent · {e.failed} failed</Badge>
              ) : (
                <Badge tone="good">{e.sent} sent</Badge>
              )}
              <span className="text-[13px] text-faint">{when(e.created_at)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
