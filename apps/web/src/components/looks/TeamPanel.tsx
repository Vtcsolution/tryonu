"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { formatPrice } from "@/components/try/shop";
import { ApiError, mediaThumb } from "@/lib/api/client";
import { community, team, type ReadyLook } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const AUDIENCES: [string, string][] = [
  ["women", "Women"],
  ["men", "Men"],
  ["kids", "Kids"],
];
const field =
  "h-11 rounded-xl border border-line-strong bg-surface px-3 text-[15px] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25";
const errText = (e: unknown) => (e instanceof ApiError ? e.detail : "Something went wrong. Please try again.");

/** tryonu.app/team: TryOnU team members turn their finished try-ons into
 * Ready looks (tryonu.app/looks) and keep them up to date. */
export function TeamPanel() {
  const { user, isLoading } = useSession();
  if (isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  if (!user || !(user.is_team || user.is_admin)) {
    return (
      <section className="tu-container py-20 text-center">
        <h1 className="font-display text-[30px] text-ink">This page is for the TryOnU team</h1>
        <p className="mt-2 text-[16px] text-muted">Ask an admin to add you as a team member.</p>
      </section>
    );
  }
  return (
    <section className="tu-container py-8 md:py-12">
      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Team panel</p>
      <h1 className="mt-1 font-display text-[clamp(30px,4vw,44px)] leading-tight text-ink">Make ready looks</h1>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <span className="rounded-full bg-sage-tint/60 px-4 py-2 text-[15px] text-ink">
          You have <b>{user.credits_balance}</b> credits. One outfit try-on uses 10.
        </span>
        <Link href="/looks" target="_blank" className="text-[15px] font-semibold text-sage-deep hover:underline">
          See the Ready looks page ↗
        </Link>
      </div>

      <ol className="mt-6 grid gap-3 md:grid-cols-3">
        {[
          ["Make the try-on", "Open Try on, add the model's photo, then type the look (for example \"women's winter coat look\") and press Try it on."],
          ["Publish it here", "Pick the finished try-on below, give it a title and choose women, men or kids."],
          ["Share it", "It's on the Ready looks page at once. Open its post picture and use it on Instagram, Facebook or TikTok."],
        ].map(([title, text], i) => (
          <li key={title} className="rounded-[18px] border border-line bg-surface p-4">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-sage text-[14px] font-semibold text-white">{i + 1}</span>
            <p className="mt-2 text-[16.5px] font-semibold text-ink">{title}</p>
            <p className="mt-1 text-[14.5px] leading-relaxed text-ink-soft">{text}</p>
          </li>
        ))}
      </ol>
      <Link href="/try" className="tu-press mt-4 inline-flex min-h-[46px] items-center rounded-full bg-sage px-5 text-[15.5px] font-semibold text-white hover:bg-sage-deep">
        Make a try-on →
      </Link>

      <Publish />
      <Published />
    </section>
  );
}

function Publish() {
  const qc = useQueryClient();
  const looks = useQuery({ queryKey: ["community", "my-looks"], queryFn: community.myLooks });
  const [jobId, setJobId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [audience, setAudience] = useState("women");
  const [season, setSeason] = useState("Winter");
  const publish = useMutation({
    mutationFn: (now: boolean) => team.publish({ tryon_job_id: jobId!, title: title.trim(), audience, season: season.trim() || null, publish: now }),
    onSuccess: () => {
      setJobId(null);
      setTitle("");
      qc.invalidateQueries({ queryKey: ["team", "looks"] });
      qc.invalidateQueries({ queryKey: ["ready-looks"] });
    },
  });

  return (
    <div className="mt-10">
      <h2 className="font-display text-[24px] text-ink">1. Publish a finished try-on</h2>
      {publish.isSuccess && (
        <p className="mt-3 rounded-[14px] bg-sage-tint/60 px-4 py-3 text-[15px] text-ink">
          {publish.data.is_published ? (
            <>
              Published. It&apos;s on the Ready looks page now.{" "}
              <Link href={`/looks/${publish.data.id}`} target="_blank" className="font-semibold text-sage-deep underline">Open it ↗</Link>
            </>
          ) : (
            <>Saved as a draft. Publish it below when it&apos;s ready (press &quot;Hidden&quot; to show it).</>
          )}
        </p>
      )}
      {looks.data && looks.data.length === 0 && (
        <p className="mt-3 text-[15px] text-muted">No finished try-ons yet. Make one first with Try on.</p>
      )}
      <div className="mt-4 flex gap-3 overflow-x-auto pb-2">
        {(looks.data ?? []).map((l) => (
          <button
            key={l.job_id}
            type="button"
            onClick={() => setJobId(l.job_id)}
            aria-pressed={jobId === l.job_id}
            className={`w-28 shrink-0 overflow-hidden rounded-xl border-2 ${jobId === l.job_id ? "border-sage" : "border-line hover:border-line-strong"}`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={mediaThumb(l.image_url, 240)} alt="A finished try-on" loading="lazy" className="aspect-[3/4] w-full bg-paper-2 object-cover object-top" />
          </button>
        ))}
      </div>
      {jobId && (
        <form
          className="mt-4 flex flex-wrap items-end gap-3 rounded-[18px] border border-line bg-surface p-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim().length >= 2) publish.mutate(true);
          }}
        >
          <label className="grid gap-1 text-[14px] text-ink-soft">
            Title
            <input id="look-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Men's winter overcoat look" maxLength={120} className={`${field} w-72 max-w-full`} />
          </label>
          <label className="grid gap-1 text-[14px] text-ink-soft">
            For
            <select id="look-audience" value={audience} onChange={(e) => setAudience(e.target.value)} className={field}>
              {AUDIENCES.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-[14px] text-ink-soft">
            Season tag
            <input id="look-season" value={season} onChange={(e) => setSeason(e.target.value)} placeholder="Winter" maxLength={24} className={`${field} w-32`} />
          </label>
          <button
            type="submit"
            disabled={publish.isPending || title.trim().length < 2}
            className="tu-press min-h-[44px] rounded-full bg-sage px-5 text-[15.5px] font-semibold text-white disabled:opacity-50"
          >
            {publish.isPending ? "Saving…" : "Publish to Ready looks"}
          </button>
          <button
            type="button"
            disabled={publish.isPending || title.trim().length < 2}
            onClick={() => publish.mutate(false)}
            className="min-h-[44px] rounded-full border border-line-strong px-5 text-[15.5px] font-semibold text-ink disabled:opacity-50"
          >
            Save as draft
          </button>
          {publish.isError && <p role="alert" className="w-full text-[14px] text-[#a4553f]">{errText(publish.error)}</p>}
        </form>
      )}
    </div>
  );
}

function Published() {
  const looks = useQuery({ queryKey: ["team", "looks"], queryFn: team.looks });
  return (
    <div className="mt-12">
      <h2 className="font-display text-[24px] text-ink">2. Your ready looks</h2>
      {looks.data && looks.data.length === 0 && <p className="mt-3 text-[15px] text-muted">Nothing published yet.</p>}
      <div className="mt-4 grid gap-5 lg:grid-cols-2">
        {(looks.data ?? []).map((look) => (
          <LookEditor key={look.id} look={look} />
        ))}
      </div>
    </div>
  );
}

function LookEditor({ look }: { look: ReadyLook }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState(look.title);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const done = () => {
    qc.invalidateQueries({ queryKey: ["team", "looks"] });
    qc.invalidateQueries({ queryKey: ["ready-looks"] });
  };
  const update = useMutation({ mutationFn: (input: Parameters<typeof team.update>[1]) => team.update(look.id, input), onSuccess: done });
  const refresh = useMutation({ mutationFn: () => team.refresh(look.id), onSuccess: done });
  const removeItem = useMutation({ mutationFn: (itemId: string) => team.removeItem(look.id, itemId), onSuccess: done });
  const remove = useMutation({ mutationFn: () => team.remove(look.id), onSuccess: done });
  const busy = update.isPending || refresh.isPending || removeItem.isPending || remove.isPending;
  const error = update.error ?? refresh.error ?? removeItem.error ?? remove.error;

  return (
    <article className={`flex gap-4 rounded-[20px] border bg-surface p-4 ${look.is_published ? "border-line" : "border-dashed border-line-strong opacity-80"}`}>
      <a href={look.card_url} target="_blank" rel="noopener" className="w-32 shrink-0 self-start overflow-hidden rounded-xl border border-line" title="Open the post picture">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={look.card_small_url} alt={look.title} loading="lazy" className="aspect-[4/5] w-full object-cover" />
      </a>
      <div className="min-w-0 flex-1 space-y-2">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim().length >= 2 && title.trim() !== look.title) update.mutate({ title: title.trim() });
          }}
        >
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} aria-label="Title" className={`${field} min-w-0 flex-1`} />
          <button type="submit" disabled={busy || title.trim() === look.title} className="rounded-full border border-line-strong px-3 text-[14px] font-semibold text-ink disabled:opacity-40">
            Save
          </button>
        </form>
        <div className="flex flex-wrap items-center gap-2 text-[14px]">
          <select
            value={look.audience}
            onChange={(e) => update.mutate({ audience: e.target.value })}
            disabled={busy}
            aria-label="Who the look is for"
            className={`${field} h-9`}
          >
            {AUDIENCES.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
          <button
            type="button"
            role="switch"
            aria-checked={look.is_published}
            disabled={busy}
            onClick={() => update.mutate({ is_published: !look.is_published })}
            className={`min-h-[36px] rounded-full px-3 font-semibold ${look.is_published ? "bg-sage text-white" : "border border-line-strong text-ink"}`}
          >
            {look.is_published ? "Showing" : "Hidden"}
          </button>
          <button type="button" disabled={busy} onClick={() => update.mutate({ sort_order: look.sort_order + 1 })} className="min-h-[36px] rounded-full border border-line px-3 text-ink" title="Show it earlier on the page">
            Move up
          </button>
        </div>
        <ul className="space-y-1">
          {look.items.map((it) => (
            <li key={it.id} className="flex items-center gap-2 text-[14px]">
              <span className="min-w-0 flex-1 truncate text-ink-soft">
                {it.name} · {formatPrice(it.price_cents, it.currency)}
              </span>
              <button
                type="button"
                disabled={busy || look.items.length === 1}
                onClick={() => removeItem.mutate(it.id)}
                aria-label={`Remove ${it.name}`}
                className="rounded-full px-2 text-[13px] text-[#a4553f] hover:underline disabled:opacity-40"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2 pt-1 text-[14px]">
          <Link href={`/looks/${look.id}`} target="_blank" className="rounded-full border border-line px-3 py-1.5 font-semibold text-ink hover:border-sage">Open page ↗</Link>
          <a href={look.card_url} target="_blank" rel="noopener" className="rounded-full border border-line px-3 py-1.5 font-semibold text-ink hover:border-sage">Post picture ↗</a>
          <button type="button" disabled={busy} onClick={() => refresh.mutate()} className="rounded-full border border-line px-3 py-1.5 font-semibold text-ink hover:border-sage">
            {refresh.isPending ? "Updating…" : "Update prices"}
          </button>
          {confirmDelete ? (
            <>
              <button type="button" disabled={busy} onClick={() => remove.mutate()} className="rounded-full bg-[#a4553f] px-3 py-1.5 font-semibold text-white">Yes, delete</button>
              <button type="button" onClick={() => setConfirmDelete(false)} className="rounded-full border border-line px-3 py-1.5 text-ink">Keep it</button>
            </>
          ) : (
            <button type="button" onClick={() => setConfirmDelete(true)} className="rounded-full border border-line px-3 py-1.5 text-[#a4553f]">Delete</button>
          )}
        </div>
        {look.created_by && <p className="text-[12.5px] text-muted">By {look.created_by}</p>}
        {error && <p role="alert" className="text-[14px] text-[#a4553f]">{errText(error)}</p>}
      </div>
    </article>
  );
}
