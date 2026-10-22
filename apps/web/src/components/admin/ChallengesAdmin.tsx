"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Medal, PLACE } from "@/components/community/extras";
import { adminCommunity, stores, type Challenge, type ChallengeInput } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText, inputClass, when } from "./ui";

// ready-made themes: one tap fills the form
const IDEAS: { title: string; description: string }[] = [
  { title: "Eid Look Week", description: "Show your best Eid outfit: traditional, modern or a mix." },
  { title: "Wedding Guest Look", description: "What would you wear to a wedding this season?" },
  { title: "Office Week", description: "Smart, simple and comfortable: your best look for work." },
  { title: "Summer Casual", description: "Light, easy, everyday outfits for the hot days." },
  { title: "Winter Layers", description: "Coats, shawls and layers: stay warm in style." },
  { title: "Best Look Under $30", description: "A full look where everything together costs under $30." },
];

const toLocal = (d: Date) => {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

type Form = { title: string; description: string; starts: string; ends: string; p1: number; p2: number; p3: number; sponsor: string };

function emptyForm(): Form {
  const now = new Date();
  return { title: "", description: "", starts: toLocal(now), ends: toLocal(new Date(now.getTime() + 7 * 86_400_000)), p1: 50, p2: 30, p3: 20, sponsor: "" };
}

function fromChallenge(c: Challenge): Form {
  return {
    title: c.title,
    description: c.description ?? "",
    starts: toLocal(new Date(c.starts_at)),
    ends: toLocal(new Date(c.ends_at)),
    p1: c.prizes[0],
    p2: c.prizes[1],
    p3: c.prizes[2],
    sponsor: c.sponsor?.slug ?? "",
  };
}

function toInput(f: Form): ChallengeInput {
  return {
    title: f.title.trim(),
    description: f.description.trim() || undefined,
    starts_at: new Date(f.starts).toISOString(),
    ends_at: new Date(f.ends).toISOString(),
    prize_1: Number(f.p1) || 0,
    prize_2: Number(f.p2) || 0,
    prize_3: Number(f.p3) || 0,
    sponsor_store_slug: f.sponsor || undefined,
  };
}

const STATE_BADGE: Record<Challenge["state"], { tone: "good" | "warn" | "neutral"; label: string }> = {
  live: { tone: "good", label: "Running now" },
  upcoming: { tone: "warn", label: "Coming up" },
  ended: { tone: "neutral", label: "Ended" },
};

/** Weekly style challenges: create one in a minute, see entries, end it early, hide a mistake. */
export function ChallengesAdmin() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["admin", "community", "challenges"], queryFn: adminCommunity.challenges });
  const [editing, setEditing] = useState<{ id: string | null; form: Form } | null>(null);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin", "community", "challenges"] });
    qc.invalidateQueries({ queryKey: ["community", "challenges"] });
  };
  const finish = useMutation({ mutationFn: (id: string) => adminCommunity.finishChallenge(id), onSuccess: refresh });
  const hide = useMutation({ mutationFn: ({ id, hidden }: { id: string; hidden: boolean }) => adminCommunity.hideChallenge(id, hidden), onSuccess: refresh });

  return (
    <div>
      <SectionHeader
        title="Style challenges"
        hint="Pick a theme and dates. The 3 most-liked looks win credits by themselves."
      >
        {!editing && (
          <SmallButton tone="primary" onClick={() => setEditing({ id: null, form: emptyForm() })}>
            ＋ New challenge
          </SmallButton>
        )}
      </SectionHeader>

      {editing && (
        <ChallengeForm
          id={editing.id}
          start={editing.form}
          onDone={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}

      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      {list.data && list.data.length === 0 && !editing && (
        <p className="rounded-[16px] border border-dashed border-line p-8 text-center text-[15px] text-muted">
          No challenges yet. Press “New challenge” and pick a ready-made theme.
        </p>
      )}
      <div className="mt-4 space-y-3">
        {list.data?.map((c) => (
          <article key={c.id} className={`rounded-[16px] border bg-surface p-4 ${c.hidden ? "border-[#c0503a]/30 opacity-70" : "border-line"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[16px] font-semibold text-ink">{c.title}</p>
              <Badge tone={STATE_BADGE[c.state].tone}>{STATE_BADGE[c.state].label}</Badge>
              {c.hidden && <Badge tone="bad">Hidden</Badge>}
              {c.sponsor && <Badge>Sponsor: {c.sponsor.name}</Badge>}
            </div>
            <p className="mt-1 text-[13.5px] text-muted">
              {when(c.starts_at)} → {when(c.ends_at)} · {c.entries} entries · prizes {c.prizes.join(" / ")} credits
            </p>
            {c.winners.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-3 text-[13.5px] text-ink">
                {c.winners.map((w) => (
                  <span key={w.place} className="inline-flex items-center gap-1.5">
                    <Medal place={w.place} size={18} /> @{w.author.handle} · {w.likes} likes · +{w.credits}
                  </span>
                ))}
              </div>
            )}
            {c.state === "ended" && c.winners.length === 0 && <p className="mt-2 text-[13.5px] text-muted">No winners (no entry got a like).</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              <Link href={`/community/challenges/${c.id}`} target="_blank" className="inline-flex h-8 items-center rounded-full border border-line-strong px-3 text-[13px] font-medium text-ink hover:border-ink/40">
                Open page ↗
              </Link>
              {c.state !== "ended" && (
                <>
                  <SmallButton onClick={() => setEditing({ id: c.id, form: fromChallenge(c) })}>Edit</SmallButton>
                  <SmallButton
                    tone="danger"
                    disabled={finish.isPending}
                    onClick={() =>
                      window.confirm(`End “${c.title}” now? The 3 most liked entries win their prizes right away.`) && finish.mutate(c.id)
                    }
                  >
                    End now & pay winners
                  </SmallButton>
                </>
              )}
              <SmallButton disabled={hide.isPending} onClick={() => hide.mutate({ id: c.id, hidden: !c.hidden })}>
                {c.hidden ? "Show again" : "Hide"}
              </SmallButton>
            </div>
          </article>
        ))}
      </div>
      {(finish.isError || hide.isError) && <ErrorNote>{errorText(finish.error ?? hide.error)}</ErrorNote>}
    </div>
  );
}

function ChallengeForm({ id, start, onDone }: { id: string | null; start: Form; onDone: () => void }) {
  const [f, setF] = useState<Form>(start);
  const storeList = useQuery({ queryKey: ["stores", "public"], queryFn: stores.publicStores });
  const save = useMutation({
    mutationFn: () => (id ? adminCommunity.updateChallenge(id, toInput(f)) : adminCommunity.createChallenge(toInput(f))),
    onSuccess: onDone,
  });
  const set = (patch: Partial<Form>) => setF((prev) => ({ ...prev, ...patch }));
  const field = "mt-1 block w-full rounded-xl border border-line-strong bg-paper px-3 py-2 text-[14.5px] text-ink outline-none focus:border-sage";
  return (
    <div className="mb-4 rounded-[18px] border border-sage/40 bg-surface p-5">
      <p className="text-[16px] font-semibold text-ink">{id ? "Edit challenge" : "New challenge"}</p>
      {!id && (
        <div className="mt-3">
          <p className="text-[13px] text-muted">Ready-made themes (tap one, then change anything):</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {IDEAS.map((i) => (
              <SmallButton key={i.title} tone={f.title === i.title ? "primary" : undefined} onClick={() => set({ title: i.title, description: i.description })}>
                {i.title}
              </SmallButton>
            ))}
          </div>
        </div>
      )}
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="text-[13.5px] font-semibold text-ink md:col-span-2">
          Title
          <input value={f.title} onChange={(e) => set({ title: e.target.value })} maxLength={120} placeholder="e.g. Eid Look Week" className={field} />
        </label>
        <label className="text-[13.5px] font-semibold text-ink md:col-span-2">
          What should members post?
          <textarea value={f.description} onChange={(e) => set({ description: e.target.value })} maxLength={2000} rows={2} className={field} />
        </label>
        <label className="text-[13.5px] font-semibold text-ink">
          Starts
          <input type="datetime-local" value={f.starts} onChange={(e) => set({ starts: e.target.value })} className={field} />
        </label>
        <label className="text-[13.5px] font-semibold text-ink">
          Ends
          <input type="datetime-local" value={f.ends} onChange={(e) => set({ ends: e.target.value })} className={field} />
        </label>
        <div className="md:col-span-2">
          <p className="text-[13.5px] font-semibold text-ink">Prize credits</p>
          <div className="mt-1 grid grid-cols-3 gap-2">
            {(["p1", "p2", "p3"] as const).map((k, i) => (
              <label key={k} className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-[13.5px] text-ink">
                <Medal place={i + 1} size={20} />
                <span className="hidden sm:inline">{PLACE[i + 1]}</span>
                <input
                  type="number"
                  min={0}
                  max={10000}
                  value={f[k]}
                  onChange={(e) => set({ [k]: Number(e.target.value) } as Partial<Form>)}
                  className="w-full min-w-0 bg-transparent text-right text-[15px] font-semibold outline-none"
                />
              </label>
            ))}
          </div>
        </div>
        <label className="text-[13.5px] font-semibold text-ink md:col-span-2">
          Sponsored by a store (optional)
          <select value={f.sponsor} onChange={(e) => set({ sponsor: e.target.value })} className={`${inputClass} mt-1 block h-10 w-full`}>
            <option value="">No sponsor</option>
            {storeList.data?.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.name} ({s.country})
              </option>
            ))}
          </select>
        </label>
      </div>
      {save.isError && <div className="mt-3"><ErrorNote>{errorText(save.error)}</ErrorNote></div>}
      <div className="mt-4 flex gap-2">
        <SmallButton onClick={onDone}>Cancel</SmallButton>
        <SmallButton tone="primary" disabled={save.isPending || f.title.trim().length < 3} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : id ? "Save changes" : "Create challenge"}
        </SmallButton>
      </div>
    </div>
  );
}
