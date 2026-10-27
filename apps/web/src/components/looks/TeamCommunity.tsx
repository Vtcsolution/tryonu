"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Avatar } from "@/components/community/parts";
import { ApiError } from "@/lib/api/client";
import { team, type ReadyLook, type TeamPerson } from "@/lib/api/endpoints";

const field =
  "h-11 rounded-xl border border-line-strong bg-surface px-3 text-[15px] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25";
const errText = (e: unknown) => (e instanceof ApiError ? e.detail : "Something went wrong. Please try again.");
const usePeople = () => useQuery({ queryKey: ["team", "people"], queryFn: team.people });

/** Add a person (photo, name, @username) the team can post looks as, or
 * change one: only the filled-in parts change. */
function PersonForm({ person, onDone }: { person?: TeamPerson; onDone: (p: TeamPerson) => void }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [name, setName] = useState(person?.name ?? "");
  const [handle, setHandle] = useState(person?.handle ?? "");
  const save = useMutation({
    mutationFn: () =>
      person
        ? team.editPerson(person.id, { name: name.trim(), handle: handle.trim(), photo })
        : team.addPerson({ name: name.trim(), handle: handle.trim(), photo: photo! }),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["team", "people"] });
      onDone(p);
    },
  });
  const ready = name.trim().length >= 2 && handle.trim().length >= 3 && (person || photo);

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-[18px] border border-line bg-surface p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) save.mutate();
      }}
    >
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        className="grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-full border-2 border-dashed border-line-strong text-center text-[13px] font-semibold text-ink-soft hover:border-sage"
        aria-label="Choose the person's photo"
      >
        {preview || person?.avatar_url ? (
          preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={preview} alt="" className="h-full w-full object-cover" />
          ) : (
            <Avatar name={person!.name} handle={person!.handle} url={person!.avatar_url} size={80} />
          )
        ) : (
          "Add photo"
        )}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0] ?? null;
          setPhoto(f);
          setPreview(f ? URL.createObjectURL(f) : null);
        }}
      />
      <label className="grid gap-1 text-[14px] text-ink-soft">
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Haseeb" maxLength={60} className={`${field} w-48`} />
      </label>
      <label className="grid gap-1 text-[14px] text-ink-soft">
        Username
        <input value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="@haseeb" maxLength={31} className={`${field} w-44`} />
      </label>
      <button
        type="submit"
        disabled={!ready || save.isPending}
        className="tu-press min-h-[44px] rounded-full bg-sage px-5 text-[15.5px] font-semibold text-white disabled:opacity-50"
      >
        {save.isPending ? "Saving…" : person ? "Save" : "Add person"}
      </button>
      {!person && <p className="w-full text-[13.5px] text-muted">Use a photo and name only with that person&apos;s permission.</p>}
      {save.isError && <p role="alert" className="w-full text-[14px] text-[#a4553f]">{errText(save.error)}</p>}
    </form>
  );
}

/** The people the team posts as, with how many posts each has. */
export function PeopleSection() {
  const people = usePeople();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  return (
    <div id="people" className="mt-12 scroll-mt-24">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-[24px] text-ink">People you post as</h2>
          <p className="mt-1 text-[15px] text-muted">A look posted to the community shows this person&apos;s photo, name and username.</p>
        </div>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="min-h-[44px] rounded-full border border-line-strong px-5 text-[15.5px] font-semibold text-ink hover:border-sage"
        >
          {adding ? "Close" : "+ Add a person"}
        </button>
      </div>
      {adding && (
        <div className="mt-4">
          <PersonForm onDone={() => setAdding(false)} />
        </div>
      )}
      {people.data && people.data.length === 0 && !adding && (
        <p className="mt-4 rounded-[18px] border border-dashed border-line-strong p-6 text-center text-[16px] text-muted">
          No people yet. Press &quot;Add a person&quot; and add their photo, name and username.
        </p>
      )}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(people.data ?? []).map((p) =>
          editing === p.id ? (
            <div key={p.id} className="sm:col-span-2 lg:col-span-3">
              <PersonForm person={p} onDone={() => setEditing(null)} />
            </div>
          ) : (
            <div key={p.id} className="flex items-center gap-3 rounded-[18px] border border-line bg-surface p-3">
              <Avatar name={p.name} handle={p.handle} url={p.avatar_url} size={52} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[16px] font-semibold text-ink">{p.name}</p>
                <p className="truncate text-[14px] text-muted">
                  @{p.handle} · {p.posts} {p.posts === 1 ? "post" : "posts"}
                </p>
              </div>
              <Link href={`/u/${p.handle}`} target="_blank" className="rounded-full border border-line px-3 py-1.5 text-[14px] font-semibold text-ink hover:border-sage">
                Profile ↗
              </Link>
              <button type="button" onClick={() => setEditing(p.id)} className="rounded-full border border-line px-3 py-1.5 text-[14px] font-semibold text-ink hover:border-sage">
                Edit
              </button>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

/** Inside a look's card: post its try-on to the community as one of the
 * team's people. There it shows as the try-on picture with the products,
 * not the outfit-receipt picture used on Ready looks. */
export function ShareToCommunity({ look }: { look: ReadyLook }) {
  const qc = useQueryClient();
  const people = usePeople();
  const [personId, setPersonId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [caption, setCaption] = useState("Tried it on before buying it. What do you think: buy or skip?");
  const [poll, setPoll] = useState(true);
  const post = useMutation({
    mutationFn: () => team.postToCommunity(look.id, { person_id: personId!, caption: caption.trim(), poll }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team", "looks"] }),
  });
  const postedAs = new Set((look.community ?? []).map((c) => c.handle));

  if (post.isSuccess) {
    return (
      <p className="mt-4 rounded-[14px] bg-sage-tint/60 px-4 py-3 text-[15px] text-ink">
        Posted as @{post.data.handle}.{" "}
        <Link href={`/community/post/${post.data.post_id}`} target="_blank" className="font-semibold text-sage-deep underline">
          See the post ↗
        </Link>
      </p>
    );
  }
  return (
    <div className="mt-4 space-y-3 border-t border-line pt-4">
      <p className="text-[15px] font-semibold text-ink">1. Post as</p>
      <div className="flex flex-wrap gap-2">
        {(people.data ?? []).map((p) => {
          const done = postedAs.has(p.handle);
          return (
            <button
              key={p.id}
              type="button"
              disabled={done}
              onClick={() => setPersonId(p.id)}
              aria-pressed={personId === p.id}
              title={done ? "Already posted as this person" : undefined}
              className={`flex items-center gap-2 rounded-full border-2 py-1 pl-1 pr-3 text-[14px] font-semibold disabled:opacity-40 ${personId === p.id ? "border-sage text-ink" : "border-line text-ink-soft hover:border-line-strong"}`}
            >
              <Avatar name={p.name} handle={p.handle} url={p.avatar_url} size={28} />@{p.handle}
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="rounded-full border border-dashed border-line-strong px-3 py-1.5 text-[14px] font-semibold text-ink hover:border-sage"
        >
          {adding ? "Close" : "+ New person"}
        </button>
      </div>
      {adding && (
        <PersonForm
          onDone={(p) => {
            setAdding(false);
            setPersonId(p.id);
          }}
        />
      )}
      <p className="text-[15px] font-semibold text-ink">2. Write the post</p>
      <textarea
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        maxLength={1000}
        rows={3}
        aria-label="Post text"
        className="w-full rounded-xl border border-line-strong bg-surface p-3 text-[15px] text-ink outline-none focus:border-sage focus:ring-2 focus:ring-sage/25"
      />
      <label className="flex items-center gap-2 text-[15px] text-ink">
        <input type="checkbox" checked={poll} onChange={(e) => setPoll(e.target.checked)} className="h-5 w-5 accent-[var(--color-sage)]" />
        Ask &quot;Buy or skip?&quot;
      </label>
      <button
        type="button"
        disabled={!personId || post.isPending}
        onClick={() => post.mutate()}
        className="tu-press min-h-[44px] w-full rounded-full bg-sage px-5 text-[15.5px] font-semibold text-white disabled:opacity-50"
      >
        {post.isPending ? "Posting…" : "3. Post to community"}
      </button>
      {post.isError && <p role="alert" className="text-[14px] text-[#a4553f]">{errText(post.error)}</p>}
    </div>
  );
}
