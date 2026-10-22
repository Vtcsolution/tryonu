"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminDevelopers, adminStores } from "@/lib/api/endpoints";
import type { AdminDeveloper, DeveloperCreditPack } from "@/lib/api/types";
import { Badge, ErrorNote, SectionHeader, SmallButton, StatTile, Table, TableSkeleton, errorText, inputClass, money } from "./ui";

/** The Developer API: who uses it, their credits, and the packs they can buy. */
export function DevelopersTab() {
  const qc = useQueryClient();
  const accounts = useQuery({ queryKey: ["admin", "developers"], queryFn: adminDevelopers.list });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "developers"] });
  const credits = useMutation({
    mutationFn: ({ id, amount, note }: { id: string; amount: number; note?: string }) => adminDevelopers.adjustCredits(id, amount, note),
    onSuccess: refresh,
  });
  const packs = useQuery({ queryKey: ["admin", "developer-packs"], queryFn: adminDevelopers.packs });
  // the developer being given free try-ons (the panel above the table)
  const [giving, setGiving] = useState<AdminDeveloper | null>(null);
  const [gift, setGift] = useState("50");
  const [note, setNote] = useState("");
  const [given, setGiven] = useState<string | null>(null);
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "active" | "suspended" }) => adminDevelopers.setStatus(id, status),
    onSuccess: refresh,
  });
  const [amounts, setAmounts] = useState<Record<string, string>>({});

  const list = accounts.data ?? [];
  const totals = {
    accounts: list.length,
    credits: list.reduce((sum, a) => sum + a.credits, 0),
    month: list.reduce((sum, a) => sum + a.tryons_30d, 0),
  };

  return (
    <div className="space-y-10">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label="Developer accounts" value={totals.accounts} />
        <StatTile label="Unused credits (try-ons owed)" value={totals.credits.toLocaleString()} />
        <StatTile label="API try-ons, last 30 days" value={totals.month.toLocaleString()} />
      </div>
      <div>
        <SectionHeader
          title="Developers"
          hint="Businesses using the try-on API on their own websites. Give free try-ons, take some back, or suspend."
        />
        {(credits.isError || setStatus.isError) && (
          <div className="mb-3"><ErrorNote>{errorText(credits.error ?? setStatus.error)}</ErrorNote></div>
        )}
        {given && <p className="mb-3 rounded-xl border border-sage/40 bg-sage/10 px-4 py-2.5 text-[14px] text-ink">{given}</p>}
        {giving && (
          <div className="mb-4 rounded-[16px] border border-sage/50 bg-surface p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[15.5px] font-semibold text-ink">
                Give free API try-ons to {giving.company_name} <span className="font-normal text-muted">({giving.owner_email})</span>
              </p>
              <SmallButton onClick={() => setGiving(null)}>Close</SmallButton>
            </div>
            <p className="mt-1 text-[13.5px] text-muted">No payment needed. They see it in their bell and console right away.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(packs.data ?? [])
                .filter((p) => p.is_active)
                .map((p) => (
                  <SmallButton key={p.id} tone={gift === String(p.tryons) ? "primary" : undefined} onClick={() => setGift(String(p.tryons))}>
                    {p.name}: {p.tryons.toLocaleString()}
                  </SmallButton>
                ))}
              <input
                type="number"
                min={1}
                value={gift}
                onChange={(e) => setGift(e.target.value)}
                className={`${inputClass} w-28`}
                aria-label="Try-ons to give"
              />
            </div>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, 200))}
              placeholder="Note for them (optional), e.g. Launch partner"
              className={`${inputClass} mt-3 w-full`}
            />
            <div className="mt-3">
              <SmallButton
                tone="primary"
                disabled={credits.isPending || !(Number(gift) > 0)}
                onClick={() =>
                  window.confirm(`Give ${Number(gift).toLocaleString()} free API try-ons to ${giving.company_name}?`) &&
                  credits.mutate(
                    { id: giving.id, amount: Number(gift), note: note.trim() },
                    {
                      onSuccess: () => {
                        setGiven(`✓ ${Number(gift).toLocaleString()} free try-ons given to ${giving.company_name}.`);
                        setGiving(null);
                        setNote("");
                      },
                    },
                  )
                }
              >
                {credits.isPending ? "Giving…" : `Give ${Number(gift || 0).toLocaleString()} try-ons free`}
              </SmallButton>
            </div>
          </div>
        )}
        {accounts.isLoading ? (
          <TableSkeleton />
        ) : accounts.isError ? (
          <ErrorNote>{errorText(accounts.error, "Couldn't load developers.")}</ErrorNote>
        ) : (
          <Table
            columns={["Developer", "Owner", "Credits", "Try-ons (30d / all)", "Keys", "Status", ""]}
            rows={list.map((a: AdminDeveloper) => [
              <div key="n">
                <p className="font-medium text-ink">{a.company_name}</p>
                {a.website && <p className="text-[12.5px] text-muted">{a.website.replace(/^https?:\/\//, "")}</p>}
              </div>,
              a.owner_email,
              <span key="c" className="font-semibold">{a.credits.toLocaleString()}</span>,
              `${a.tryons_30d} / ${a.tryons_total}`,
              a.keys,
              <Badge key="s" tone={a.status === "active" ? "good" : "bad"}>{a.status}</Badge>,
              <div key="x" className="flex flex-wrap items-center gap-1.5">
                <input
                  type="number"
                  min={1}
                  value={amounts[a.id] ?? "10"}
                  onChange={(e) => setAmounts({ ...amounts, [a.id]: e.target.value })}
                  className={`${inputClass} w-20`}
                  aria-label="Credits"
                />
                <SmallButton
                  tone="primary"
                  disabled={credits.isPending}
                  onClick={() => {
                    setGiving(a);
                    setGiven(null);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  🎁 Give free
                </SmallButton>
                <SmallButton disabled={credits.isPending || a.credits === 0} onClick={() => credits.mutate({ id: a.id, amount: -Number(amounts[a.id] ?? 10) })}>
                  − Take back
                </SmallButton>
                <SmallButton
                  tone={a.status === "active" ? "danger" : "primary"}
                  disabled={setStatus.isPending}
                  onClick={() => setStatus.mutate({ id: a.id, status: a.status === "active" ? "suspended" : "active" })}
                >
                  {a.status === "active" ? "Suspend" : "Re-activate"}
                </SmallButton>
              </div>,
            ])}
            empty="No developers yet. They sign up at tryonu.app/developers/sign-up."
          />
        )}
      </div>
      <PacksEditor />
    </div>
  );
}

function PacksEditor() {
  const qc = useQueryClient();
  const packs = useQuery({ queryKey: ["admin", "developer-packs"], queryFn: adminDevelopers.packs });
  const costs = useQuery({ queryKey: ["admin", "store-costs"], queryFn: adminStores.costs });
  return (
    <div>
      <SectionHeader
        title="Credit packs"
        hint={
          costs.data
            ? `What developers pay. Each try-on costs you about ${money(costs.data.tryon_cost_usd_cents, "usd")} (FASHN); each pack shows what you keep.`
            : "What developers pay for API try-ons."
        }
      />
      {packs.isLoading ? (
        <TableSkeleton />
      ) : (
        <div className="space-y-3">
          {(packs.data ?? []).map((p) => (
            <PackRow
              key={p.id}
              pack={p}
              costCents={costs.data?.tryon_cost_usd_cents ?? null}
              onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "developer-packs"] })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PackRow({ pack, costCents, onSaved }: { pack: DeveloperCreditPack; costCents: number | null; onSaved: () => void }) {
  const [name, setName] = useState(pack.name);
  const [price, setPrice] = useState((pack.price_cents / 100).toFixed(2));
  const [tryons, setTryons] = useState(String(pack.tryons));
  const save = useMutation({
    mutationFn: (input: Parameters<typeof adminDevelopers.updatePack>[1]) => adminDevelopers.updatePack(pack.id, input),
    onSuccess: onSaved,
  });
  const priceCents = Math.round(Number(price) * 100);
  const count = Number(tryons);
  const valid = name.trim() && priceCents > 0 && count > 0;
  const cost = costCents !== null ? count * costCents : null;
  const margin = cost !== null && priceCents > 0 ? Math.round(((priceCents - cost) / priceCents) * 100) : null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[16px] border border-line bg-surface p-3">
      <input value={name} onChange={(e) => setName(e.target.value)} className={`${inputClass} w-36`} aria-label="Pack name" />
      <label className="flex items-center gap-1 text-[13px] text-muted">
        Price ({pack.currency.toUpperCase()})
        <input type="number" min={0.01} step={0.01} value={price} onChange={(e) => setPrice(e.target.value)} className={`${inputClass} w-24`} />
      </label>
      <label className="flex items-center gap-1 text-[13px] text-muted">
        Try-ons
        <input type="number" min={1} value={tryons} onChange={(e) => setTryons(e.target.value)} className={`${inputClass} w-24`} />
      </label>
      <SmallButton tone="primary" disabled={!valid || save.isPending} onClick={() => save.mutate({ name: name.trim(), price_cents: priceCents, tryons: count })}>
        {save.isPending ? "Saving…" : "Save"}
      </SmallButton>
      <SmallButton tone={pack.is_active ? "danger" : "primary"} disabled={save.isPending} onClick={() => save.mutate({ is_active: !pack.is_active })}>
        {pack.is_active ? "Hide pack" : "Offer pack"}
      </SmallButton>
      {margin !== null && cost !== null && (
        <span className={`w-full text-[13px] ${margin < 25 ? "text-[#a4553f]" : "text-sage-deep"}`}>
          {money(Math.round(priceCents / Math.max(count, 1)), pack.currency)} per try-on · costs you {money(cost, "usd")}, you keep{" "}
          {money(priceCents - cost, "usd")} ({margin}% before PayPal&apos;s fee)
        </span>
      )}
      {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
    </div>
  );
}
