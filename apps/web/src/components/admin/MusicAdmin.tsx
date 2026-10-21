"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { MOODS } from "@/components/community/Music";
import { resolveMediaUrl } from "@/lib/api/client";
import { adminMusic } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText, inputClass } from "./ui";

const KEY = ["admin", "music"];

/** The free music library: songs members can add to their posts (played in Reels). */
export function MusicAdmin() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: KEY, queryFn: adminMusic.list });
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [mood, setMood] = useState("");
  const [pct, setPct] = useState(0);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: KEY });
    qc.invalidateQueries({ queryKey: ["community", "music"] });
  };
  const add = useMutation({
    mutationFn: () => adminMusic.add(file!, title.trim(), artist.trim(), mood, setPct),
    onSuccess: () => {
      setFile(null);
      setTitle("");
      setArtist("");
      setMood("");
      setPct(0);
      refresh();
    },
  });
  const toggle = useMutation({ mutationFn: ({ id, on }: { id: string; on: boolean }) => adminMusic.update(id, { is_active: on }), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (id: string) => adminMusic.remove(id), onSuccess: refresh });

  return (
    <div>
      <SectionHeader
        title="Music library"
        hint="Songs members can add to their posts. They play in Reels. Only add music TryOnU may use: royalty-free songs (for example from Pixabay Music or FreePD) or your own. Never TikTok or film songs."
      />
      <div className="rounded-[16px] border border-line bg-surface p-4">
        <div className="flex flex-wrap items-center gap-3">
          <SmallButton onClick={() => fileRef.current?.click()}>{file ? "Choose another file" : "Choose a song file (MP3)"}</SmallButton>
          {file && <span className="text-[14px] text-ink-soft">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</span>}
          <input
            ref={fileRef}
            type="file"
            accept="audio/mpeg,audio/mp4,audio/x-m4a,audio/ogg,audio/wav,.mp3,.m4a,.ogg,.wav"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").slice(0, 120));
              e.target.value = "";
            }}
          />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <label className="text-[13.5px] font-medium text-ink-soft">
            Song name
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} className={`${inputClass} mt-1 w-full`} />
          </label>
          <label className="text-[13.5px] font-medium text-ink-soft">
            Artist (optional)
            <input value={artist} onChange={(e) => setArtist(e.target.value)} maxLength={120} className={`${inputClass} mt-1 w-full`} />
          </label>
          <label className="text-[13.5px] font-medium text-ink-soft">
            Mood (optional)
            <select value={mood} onChange={(e) => setMood(e.target.value)} className={`${inputClass} mt-1 w-full`}>
              <option value="">—</option>
              {MOODS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {add.isError && (
          <div className="mt-2">
            <ErrorNote>{errorText(add.error)}</ErrorNote>
          </div>
        )}
        <div className="mt-3">
          <SmallButton tone="primary" disabled={!file || !title.trim() || add.isPending} onClick={() => add.mutate()}>
            {add.isPending ? `Uploading… ${pct}%` : "Add to the library"}
          </SmallButton>
        </div>
      </div>

      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      {list.data && list.data.length === 0 && (
        <p className="mt-4 rounded-[16px] border border-dashed border-line p-8 text-center text-[15px] text-muted">
          No songs yet. Members see “Add music” when posting once you add the first one.
        </p>
      )}
      <div className="mt-4 space-y-2">
        {list.data?.map((t) => (
          <div key={t.id} className={`flex flex-wrap items-center gap-3 rounded-[14px] border bg-surface p-3 ${t.is_active ? "border-line" : "border-line opacity-60"}`}>
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 text-[15px] font-semibold text-ink">
                {t.title}
                {t.mood && <Badge>{MOODS.find((m) => m.id === t.mood)?.label ?? t.mood}</Badge>}
                {!t.is_active && <Badge tone="warn">Hidden</Badge>}
              </p>
              <p className="text-[13px] text-muted">
                {t.artist ? `${t.artist} · ` : ""}used on {t.uses} post{t.uses === 1 ? "" : "s"} · {(t.size_bytes / 1024 / 1024).toFixed(1)} MB
              </p>
            </div>
            <audio src={resolveMediaUrl(t.url)} controls preload="none" className="h-9 w-[240px] max-w-full" />
            <SmallButton disabled={toggle.isPending} onClick={() => toggle.mutate({ id: t.id, on: !t.is_active })}>
              {t.is_active ? "Hide" : "Show"}
            </SmallButton>
            <SmallButton
              tone="danger"
              disabled={remove.isPending}
              onClick={() => window.confirm(`Delete “${t.title}”? It also stops playing on the ${t.uses} post(s) that use it.`) && remove.mutate(t.id)}
            >
              Delete
            </SmallButton>
          </div>
        ))}
      </div>
    </div>
  );
}
