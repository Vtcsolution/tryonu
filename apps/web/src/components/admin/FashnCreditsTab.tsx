"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { adminOps } from "@/lib/api/endpoints";
import { Badge, ErrorNote, SectionHeader, SmallButton, StatTile, TableSkeleton, errorText, inputClass } from "./ui";

/** Approve live FASHN credits from the panel: the same guard and exact
 *  phrase as the command line, so nothing is ever spent without you. */
export function FashnCreditsTab() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["admin", "fashn-approval"], queryFn: adminOps.fashnStatus, refetchInterval: 30_000 });
  const [credits, setCredits] = useState("40");
  const [hours, setHours] = useState("24");
  const [phrase, setPhrase] = useState("");
  const done = (data: Awaited<ReturnType<typeof adminOps.fashnStatus>>) => {
    qc.setQueryData(["admin", "fashn-approval"], data);
    setPhrase("");
  };
  const approve = useMutation({ mutationFn: () => adminOps.fashnApprove(Number(credits), Number(hours), phrase), onSuccess: done });
  const close = useMutation({ mutationFn: adminOps.fashnClose, onSuccess: done });
  const resume = useMutation({ mutationFn: adminOps.fashnResume, onSuccess: done });

  if (status.isLoading) return <TableSkeleton />;
  if (status.isError || !status.data) return <ErrorNote>{errorText(status.error, "Couldn't load the FASHN approval.")}</ErrorNote>;
  const s = status.data;
  const open = s.open_authorizations[0];
  const left = open ? open.budget - open.reserved : 0;
  const expected = `AUTHORIZE ${Number(credits) || 0} FASHN CREDITS`;

  return (
    <div className="space-y-8">
      <SectionHeader
        title="FASHN credits"
        hint="Try-ons run by themselves. A daily limit keeps costs safe (about 4 FASHN credits per look). Change it in Settings & keys → Credits & prices."
      />
      {s.automatic && (
        <div
          className={`flex flex-wrap items-center gap-3 rounded-[20px] border p-5 ${
            s.automatic.paused ? "border-[#c0503a]/40 bg-[#c0503a]/10" : "border-sage/40 bg-sage-tint/25"
          }`}
        >
          <div className="min-w-0 flex-1">
            <p className="text-[17px] font-semibold text-ink">
              Automatic try-ons: {s.automatic.paused ? "PAUSED" : s.automatic.daily_credits > 0 ? "ON" : "OFF"}
            </p>
            <p className="mt-1 text-[14px] text-ink-soft">
              Today: {s.automatic.used_today} of {s.automatic.daily_credits} FASHN credits used · about{" "}
              {Math.floor(s.automatic.left_today / 4)} more looks · resets at midnight (UTC)
            </p>
          </div>
          {s.automatic.paused ? (
            <SmallButton tone="primary" disabled={resume.isPending} onClick={() => resume.mutate()}>
              {resume.isPending ? "Resuming…" : "Resume try-ons"}
            </SmallButton>
          ) : (
            <SmallButton tone="danger" disabled={close.isPending} onClick={() => close.mutate()}>
              {close.isPending ? "Pausing…" : "Pause all try-ons"}
            </SmallButton>
          )}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Try-ons" value={s.live_generation_allowed ? "Running" : "Paused"} tone={s.live_generation_allowed ? undefined : "warn"} />
        <StatTile label="Approved credits left" value={open ? `${left} of ${open.budget}` : "None open"} tone={open && left < 8 ? "warn" : undefined} />
        <StatTile label="Approval ends" value={open ? new Date(open.expires_at).toLocaleString() : "—"} />
        <StatTile label="Spent, all time" value={s.counted_as_spent_credits_all_time} />
      </div>
      {open && (
        <div className="flex flex-wrap items-center gap-3 rounded-[16px] border border-line bg-surface p-4 text-[14px]">
          <Badge tone="good">Open</Badge>
          <span className="text-ink-soft">
            {open.reserved} used of {open.budget} · about {Math.floor(left / 4)} more looks
          </span>
          <SmallButton tone="danger" disabled={close.isPending} onClick={() => close.mutate()}>
            {close.isPending ? "Closing…" : "Close it now"}
          </SmallButton>
        </div>
      )}

      <form
        className="space-y-3 rounded-[20px] border border-line bg-surface p-5"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (phrase.trim()) approve.mutate();
        }}
      >
        <p className="text-[15px] font-semibold text-ink">Extra FASHN credits (optional)</p>
        <p className="text-[13.5px] text-muted">Only needed on a very busy day, on top of the automatic daily limit.</p>
        {open && left > 0 && (
          <p className="text-[13.5px] text-muted">An approval with credits left is open: close it first to open a new one.</p>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-[13px] text-muted">
            Credits (max {s.max_credits_per_authorization})
            <input type="number" min={1} max={s.max_credits_per_authorization} value={credits} onChange={(e) => setCredits(e.target.value)} className={`${inputClass} mt-1 block w-28`} />
          </label>
          <label className="text-[13px] text-muted">
            Hours open (max {s.max_hours})
            <input type="number" min={1} max={s.max_hours} value={hours} onChange={(e) => setHours(e.target.value)} className={`${inputClass} mt-1 block w-28`} />
          </label>
          <label className="min-w-[260px] flex-1 text-[13px] text-muted">
            Type exactly: <b className="text-ink">{expected}</b>
            <input value={phrase} onChange={(e) => setPhrase(e.target.value)} placeholder={expected} className={`${inputClass} mt-1 block w-full`} autoComplete="off" />
          </label>
          <SmallButton type="submit" tone="primary" disabled={approve.isPending || phrase.trim() !== expected}>
            {approve.isPending ? "Approving…" : "Approve"}
          </SmallButton>
        </div>
        {(approve.isError || close.isError || resume.isError) && <ErrorNote>{errorText(approve.error ?? close.error ?? resume.error)}</ErrorNote>}
      </form>
    </div>
  );
}
