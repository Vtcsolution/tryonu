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
    mutationFn: ({ id, amount }: { id: string; amount: number }) => adminDevelopers.adjustCredits(id, amount),
    onSuccess: refresh,
  });
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
          hint="Businesses using TryOnU's try-on API on their own sites. Their try-ons run automatically within the credits they paid for, up to the daily limit in Settings → Credits & pricing. Developer credits are separate from shopper credits and store try-on credits."
        />
        {(credits.isError || setStatus.isError) && (
          <div className="mb-3"><ErrorNote>{errorText(credits.error ?? setStatus.error)}</ErrorNote></div>
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
                <SmallButton tone="primary" disabled={credits.isPending} onClick={() => credits.mutate({ id: a.id, amount: Number(amounts[a.id] ?? 10) })}>
                  + Add
                </SmallButton>
                <SmallButton disabled={credits.isPending || a.credits === 0} onClick={() => credits.mutate({ id: a.id, amount: -Number(amounts[a.id] ?? 10) })}>
                  − Take
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
