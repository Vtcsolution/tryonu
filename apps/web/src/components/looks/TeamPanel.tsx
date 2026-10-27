"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { formatPrice } from "@/components/try/shop";
import { ApiError, mediaThumb } from "@/lib/api/client";
import { community, team, type ReadyLook } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import { PeopleSection, ShareToCommunity } from "./TeamCommunity";

const AUDIENCES: [string, string][] = [
  ["women", "Women"],
  ["men", "Men"],
  ["kids", "Kids"],
];
const audienceName = (a: string) => AUDIENCES.find(([v]) => v === a)?.[1] ?? a;
const field =
  "h-11 rounded-xl border border-line-strong bg-surface px-3 text-[15px] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25";
const errText = (e: unknown) => (e instanceof ApiError ? e.detail : "Something went wrong. Please try again.");
const shortDate = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";

/** tryonu.app/team: TryOnU team members turn their finished try-ons into
 * Ready looks (tryonu.app/looks), see how many they've made, and keep them
 * up to date. */
export function TeamPanel() {
  const { user, isLoading } = useSession();
  if (isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  if (!user) {
    return (
      <section className="tu-container py-20 text-center">
        <h1 className="font-display text-[30px] text-ink">Team panel</h1>
        <p className="mt-2 text-[16px] text-muted">Sign in with your team account to open it.</p>
        <Link
          href="/sign-in?next=/team"
          className="mt-6 inline-flex rounded-full bg-sage px-6 py-3 text-[16px] font-semibold text-white hover:bg-sage-deep"
        >
          Sign in
        </Link>
      </section>
    );
  }
  if (!(user.is_team || user.is_admin)) {
    return (
      <section className="tu-container py-20 text-center">
        <h1 className="font-display text-[30px] text-ink">This page is for the TryOnU team</h1>
        <p className="mt-2 text-[16px] text-muted">
          You are signed in as {user.email}, which is not a team account. Ask an admin to add you, or sign in with your team account.
        </p>
      </section>
    );
  }
  return <Panel name={(user.full_name || "").split(" ")[0]} credits={user.credits_balance} />;
}

function Panel({ name, credits }: { name: string; credits: number }) {
  const looks = useQuery({ queryKey: ["team", "looks"], queryFn: team.looks });
  const all = looks.data ?? [];
  const mine = all.filter((l) => l.mine);
  const showing = mine.filter((l) => l.is_published).length;
  const stats: [string, number | string, string][] = [
    ["Looks you made", looks.data ? mine.length : "…", "#my-looks"],
    ["On the site now", looks.data ? showing : "…", "#my-looks"],
    ["Drafts", looks.data ? mine.length - showing : "…", "#my-looks"],
    ["Try-ons left", Math.floor(credits / 10), "/try"],
  ];

  return (
    <section className="tu-container py-8 md:py-12">
      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Team panel</p>
      <h1 className="mt-1 font-display text-[clamp(30px,4vw,44px)] leading-tight text-ink">
        {name ? `Hi ${name}, ` : ""}your ready looks
      </h1>

      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map(([label, value, href]) => (
          <Link key={label} href={href} className="rounded-[18px] border border-line bg-surface p-4 transition-colors hover:border-sage">
            <p className="font-display text-[34px] leading-none text-ink">{value}</p>
            <p className="mt-2 text-[15px] text-ink-soft">{label}</p>
          </Link>
        ))}
      </div>
      <p className="mt-2 text-[14px] text-muted">You have {credits} credits. One outfit try-on uses 10.</p>

      <h2 className="mt-10 font-display text-[24px] text-ink">Make a new look in 3 steps</h2>
      <ol className="mt-4 grid gap-3 md:grid-cols-3">
        {[
          ["Make a try-on", "Add the model's photo and the clothes, then press Try it on.", "/try", "Open Try on"],
          ["Publish it", "Pick the finished try-on below, give it a title and press Publish.", "#publish", "Go to step 2"],
          ["Share it", "Press \"Post to community\" on your look, or use its picture on Instagram, Facebook or TikTok.", "#my-looks", "See my looks"],
        ].map(([title, text, href, action], i) => (
          <li key={title} className="flex flex-col rounded-[18px] border border-line bg-surface p-4">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-sage text-[15px] font-semibold text-white">{i + 1}</span>
            <p className="mt-2 text-[17px] font-semibold text-ink">{title}</p>
            <p className="mt-1 flex-1 text-[15px] leading-relaxed text-ink-soft">{text}</p>
            <Link
              href={href}
              className="tu-press mt-3 inline-flex min-h-[42px] items-center justify-center rounded-full border border-line-strong px-4 text-[15px] font-semibold text-ink hover:border-sage"
            >
              {action}
            </Link>
          </li>
        ))}
      </ol>

      <Publish published={new Set(all.map((l) => l.tryon_job_id).filter(Boolean) as string[])} />
      <Looks all={all} mine={mine} loading={looks.isLoading} />
      <PeopleSection />
    </section>
  );
}

function Publish({ published }: { published: Set<string> }) {
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
    <div id="publish" className="mt-12 scroll-mt-24">
      <h2 className="font-display text-[24px] text-ink">Step 2: publish a finished try-on</h2>
      <p className="mt-1 text-[15px] text-muted">Tap a picture, then fill in the title.</p>
      {publish.isSuccess && (
        <p className="mt-3 rounded-[14px] bg-sage-tint/60 px-4 py-3 text-[15px] text-ink">
          {publish.data.is_published ? (
            <>
              Published. It&apos;s on the Ready looks page now.{" "}
              <Link href={`/looks/${publish.data.id}`} target="_blank" className="font-semibold text-sage-deep underline">Visit it ↗</Link>
            </>
          ) : (
            <>Saved as a draft. Find it under My looks and press &quot;Publish it&quot; when it&apos;s ready.</>
          )}
        </p>
      )}
      {looks.data && looks.data.length === 0 && (
        <p className="mt-3 text-[15px] text-muted">No finished try-ons yet. Make one first with Try on.</p>
      )}
      <div className="mt-4 flex gap-3 overflow-x-auto pb-2">
        {(looks.data ?? []).map((l) => {
          const done = published.has(l.job_id);
          return (
            <button
              key={l.job_id}
              type="button"
              onClick={() => setJobId(l.job_id)}
              aria-pressed={jobId === l.job_id}
              className={`relative w-28 shrink-0 overflow-hidden rounded-xl border-2 ${jobId === l.job_id ? "border-sage" : "border-line hover:border-line-strong"}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={mediaThumb(l.image_url, 240)} alt="A finished try-on" loading="lazy" className="aspect-[3/4] w-full bg-paper-2 object-cover object-top" />
              {done && (
                <span className="absolute inset-x-0 bottom-0 bg-ink/75 py-1 text-center text-[12px] font-semibold text-white">Already used</span>
              )}
            </button>
          );
        })}
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
            {publish.isPending ? "Saving…" : "Publish"}
          </button>
          <button
            type="button"
            disabled={publish.isPending || title.trim().length < 2}
            onClick={() => publish.mutate(false)}
            className="min-h-[44px] rounded-full border border-line-strong px-5 text-[15.5px] font-semibold text-ink disabled:opacity-50"
          >
            Save as draft
          </button>
          {published.has(jobId) && (
            <p className="w-full text-[14px] text-muted">This try-on is already a ready look. Publishing it again makes a second copy.</p>
          )}
          {publish.isError && <p role="alert" className="w-full text-[14px] text-[#a4553f]">{errText(publish.error)}</p>}
        </form>
      )}
    </div>
  );
}

type Show = "all" | "on" | "draft";

function Looks({ all, mine, loading }: { all: ReadyLook[]; mine: ReadyLook[]; loading: boolean }) {
  const [whose, setWhose] = useState<"mine" | "team">("mine");
  const [show, setShow] = useState<Show>("all");
  const base = whose === "mine" ? mine : all;
  const list = base.filter((l) => (show === "on" ? l.is_published : show === "draft" ? !l.is_published : true));
  const chip = (active: boolean) =>
    `min-h-[40px] rounded-full px-4 text-[15px] font-semibold ${active ? "bg-ink text-paper" : "border border-line-strong text-ink hover:border-sage"}`;

  return (
    <div id="my-looks" className="mt-12 scroll-mt-24">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-[24px] text-ink">{whose === "mine" ? "My looks" : "All team looks"}</h2>
        <div className="flex gap-2" role="tablist">
          <button type="button" role="tab" aria-selected={whose === "mine"} onClick={() => setWhose("mine")} className={chip(whose === "mine")}>
            Mine ({mine.length})
          </button>
          <button type="button" role="tab" aria-selected={whose === "team"} onClick={() => setWhose("team")} className={chip(whose === "team")}>
            Whole team ({all.length})
          </button>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {(
          [
            ["all", `All (${base.length})`],
            ["on", `On the site (${base.filter((l) => l.is_published).length})`],
            ["draft", `Drafts (${base.filter((l) => !l.is_published).length})`],
          ] as [Show, string][]
        ).map(([v, label]) => (
          <button key={v} type="button" aria-pressed={show === v} onClick={() => setShow(v)} className={chip(show === v)}>
            {label}
          </button>
        ))}
      </div>

      {loading && <div className="mx-auto my-12 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />}
      {!loading && list.length === 0 && (
        <p className="mt-6 rounded-[18px] border border-dashed border-line-strong p-6 text-center text-[16px] text-muted">
          {whose === "mine" && mine.length === 0
            ? "You haven't made a look yet. Start with step 1 above."
            : "Nothing here yet."}
        </p>
      )}
      <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {list.map((look) => (
          <LookCard key={look.id} look={look} />
        ))}
      </div>
    </div>
  );
}

function LookCard({ look }: { look: ReadyLook }) {
  const [open, setOpen] = useState<"edit" | "community" | null>(null);
  const toggle = (what: "edit" | "community") => setOpen((v) => (v === what ? null : what));
  return (
    <article className={`overflow-hidden rounded-[20px] border bg-surface ${look.is_published ? "border-line" : "border-dashed border-line-strong"}`}>
      <Link href={`/looks/${look.id}`} target="_blank" className="relative block bg-paper-2" title="Visit this look">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={look.card_small_url} alt={look.title} loading="lazy" className="aspect-[4/5] w-full object-cover" />
        <span
          className={`absolute left-3 top-3 rounded-full px-3 py-1 text-[13px] font-semibold ${look.is_published ? "bg-sage text-white" : "bg-ink/80 text-white"}`}
        >
          {look.is_published ? "On the site" : "Draft"}
        </span>
      </Link>
      <div className="p-4">
        <p className="line-clamp-2 text-[17px] font-semibold leading-snug text-ink">{look.title}</p>
        <p className="mt-1 text-[14px] text-muted">
          {audienceName(look.audience)} · {look.items.length} {look.items.length === 1 ? "product" : "products"}
          {look.total_cents != null && look.currency ? ` · ${formatPrice(look.total_cents, look.currency)}` : ""}
        </p>
        <p className="text-[13.5px] text-muted">
          {shortDate(look.created_at)}
          {!look.mine && look.created_by ? ` · by ${look.created_by}` : ""}
        </p>
        {look.community && look.community.length > 0 && (
          <p className="mt-1 text-[13.5px] text-ink-soft">
            In community as{" "}
            {look.community.map((c, i) => (
              <span key={c.post_id}>
                {i > 0 && ", "}
                <Link href={`/community/post/${c.post_id}`} target="_blank" className="font-semibold text-sage-deep hover:underline">@{c.handle}</Link>
              </span>
            ))}
          </p>
        )}
        <div className="mt-3 flex gap-2">
          <Link
            href={`/looks/${look.id}`}
            target="_blank"
            className="tu-press inline-flex min-h-[44px] flex-1 items-center justify-center rounded-full bg-sage px-4 text-[15.5px] font-semibold text-white hover:bg-sage-deep"
          >
            Visit ↗
          </Link>
          <button
            type="button"
            onClick={() => toggle("edit")}
            aria-expanded={open === "edit"}
            className="min-h-[44px] flex-1 rounded-full border border-line-strong px-4 text-[15.5px] font-semibold text-ink hover:border-sage"
          >
            {open === "edit" ? "Close" : "Edit"}
          </button>
        </div>
        {look.tryon_job_id && (
          <button
            type="button"
            onClick={() => toggle("community")}
            aria-expanded={open === "community"}
            className="mt-2 min-h-[44px] w-full rounded-full border border-line-strong px-4 text-[15.5px] font-semibold text-ink hover:border-sage"
          >
            {open === "community" ? "Close" : "Post to community"}
          </button>
        )}
        {open === "edit" && <LookEditor look={look} />}
        {open === "community" && <ShareToCommunity look={look} />}
      </div>
    </article>
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
  const small = "min-h-[38px] rounded-full border border-line px-3 text-[14px] font-semibold text-ink hover:border-sage disabled:opacity-40";

  return (
    <div className="mt-4 space-y-3 border-t border-line pt-4">
      <button
        type="button"
        disabled={busy}
        onClick={() => update.mutate({ is_published: !look.is_published })}
        className={`min-h-[44px] w-full rounded-full text-[15.5px] font-semibold ${look.is_published ? "border border-line-strong text-ink" : "bg-sage text-white"}`}
      >
        {look.is_published ? "Hide it (make it a draft)" : "Publish it on the site"}
      </button>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim().length >= 2 && title.trim() !== look.title) update.mutate({ title: title.trim() });
        }}
      >
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} aria-label="Title" className={`${field} min-w-0 flex-1`} />
        <button type="submit" disabled={busy || title.trim() === look.title} className={small}>
          Save
        </button>
      </form>
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={look.audience}
          onChange={(e) => update.mutate({ audience: e.target.value })}
          disabled={busy}
          aria-label="Who the look is for"
          className={`${field} h-[38px]`}
        >
          {AUDIENCES.map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <button type="button" disabled={busy} onClick={() => update.mutate({ sort_order: look.sort_order + 1 })} className={small} title="Show it earlier on the page">
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
      <div className="flex flex-wrap gap-2">
        <a href={look.card_url} target="_blank" rel="noopener" className={`${small} inline-flex items-center`}>Post picture ↗</a>
        <button type="button" disabled={busy} onClick={() => refresh.mutate()} className={small}>
          {refresh.isPending ? "Updating…" : "Update prices"}
        </button>
        {confirmDelete ? (
          <>
            <button type="button" disabled={busy} onClick={() => remove.mutate()} className="min-h-[38px] rounded-full bg-[#a4553f] px-3 text-[14px] font-semibold text-white">Yes, delete</button>
            <button type="button" onClick={() => setConfirmDelete(false)} className={small}>Keep it</button>
          </>
        ) : (
          <button type="button" onClick={() => setConfirmDelete(true)} className="min-h-[38px] rounded-full border border-line px-3 text-[14px] text-[#a4553f]">Delete</button>
        )}
      </div>
      {error && <p role="alert" className="text-[14px] text-[#a4553f]">{errText(error)}</p>}
    </div>
  );
}
