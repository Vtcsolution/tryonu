"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminStores } from "@/lib/api/endpoints";
import type { AdminStore, StorePlan } from "@/lib/api/types";
import { countryName } from "@/lib/countries";
import { Badge, ErrorNote, SectionHeader, SmallButton, Table, TableSkeleton, errorText, inputClass, money } from "./ui";

const FILTERS: [string, string][] = [
  ["pending", "Waiting"],
  ["approved", "Approved"],
  ["suspended", "Suspended"],
  ["rejected", "Rejected"],
  ["", "All"],
];
const TONE: Record<string, "good" | "bad" | "warn" | "neutral"> = {
  pending: "warn",
  approved: "good",
  rejected: "bad",
  suspended: "bad",
};

/** Company stores: approve new ones, suspend bad ones, and set plan prices. */
export function StoresTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState("pending");
  const stores = useQuery({ queryKey: ["admin", "stores", filter], queryFn: () => adminStores.list(filter || undefined) });
  const setStatus = useMutation({
    mutationFn: ({ store, status }: { store: AdminStore; status: string }) => {
      const note =
        status === "rejected" || status === "suspended"
          ? window.prompt(`Reason shown to ${store.name} (optional):`) ?? undefined
          : undefined;
      return adminStores.setStatus(store.id, status, note);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "stores"] }),
  });

  return (
    <div className="space-y-10">
      <div>
        <SectionHeader
          title="Company stores"
          hint="New stores wait here for approval. A store's products reach shoppers only when it is approved AND has a paid plan."
        />
        <div className="mb-4 flex flex-wrap gap-1.5">
          {FILTERS.map(([value, label]) => (
            <SmallButton key={value || "all"} tone={filter === value ? "primary" : "neutral"} onClick={() => setFilter(value)}>
              {label}
            </SmallButton>
          ))}
        </div>
        {setStatus.isError && <div className="mb-3"><ErrorNote>{errorText(setStatus.error)}</ErrorNote></div>}
        {stores.isLoading ? (
          <TableSkeleton />
        ) : stores.isError || !stores.data ? (
          <ErrorNote>{errorText(stores.error, "Couldn't load stores.")}</ErrorNote>
        ) : (
          <Table
            columns={["Store", "Country", "Owner", "Plan", "Products", "Status", ""]}
            rows={stores.data.map((s) => [
              <div key="n">
                <p className="font-medium text-ink">{s.name}</p>
                {s.website_url && (
                  <a href={s.website_url} target="_blank" rel="noopener noreferrer" className="text-[11.5px] text-sage-deep hover:underline">
                    {s.website_url.replace(/^https?:\/\//, "")}
                  </a>
                )}
              </div>,
              countryName(s.country),
              s.owner_email,
              s.plan_active ? `${s.plan_code} until ${new Date(s.plan_expires_at!).toLocaleDateString()}` : "None",
              `${s.product_count} / ${s.plan_active ? s.plan_product_limit : 0}`,
              <Badge key="s" tone={TONE[s.status] ?? "neutral"}>{s.status}</Badge>,
              <div key="a" className="flex flex-wrap gap-1.5">
                {s.status !== "approved" && (
                  <SmallButton tone="primary" disabled={setStatus.isPending} onClick={() => setStatus.mutate({ store: s, status: "approved" })}>
                    Approve
                  </SmallButton>
                )}
                {s.status === "pending" && (
                  <SmallButton tone="danger" disabled={setStatus.isPending} onClick={() => setStatus.mutate({ store: s, status: "rejected" })}>
                    Reject
                  </SmallButton>
                )}
                {s.status === "approved" && (
                  <SmallButton tone="danger" disabled={setStatus.isPending} onClick={() => setStatus.mutate({ store: s, status: "suspended" })}>
                    Suspend
                  </SmallButton>
                )}
              </div>,
            ])}
            empty="No stores here."
          />
        )}
      </div>
      <PlansEditor />
    </div>
  );
}

function PlansEditor() {
  const qc = useQueryClient();
  const plans = useQuery({ queryKey: ["admin", "store-plans"], queryFn: adminStores.plans });
  return (
    <div>
      <SectionHeader title="Store plans" hint="What companies pay for a 30-day pass and how many products each plan lists. Changes apply to the next purchase." />
      {plans.isLoading ? (
        <TableSkeleton />
      ) : plans.isError || !plans.data ? (
        <ErrorNote>{errorText(plans.error, "Couldn't load plans.")}</ErrorNote>
      ) : (
        <div className="space-y-3">
          {plans.data.map((p) => (
            <PlanRow key={p.id} plan={p} onSaved={() => qc.invalidateQueries({ queryKey: ["admin", "store-plans"] })} />
          ))}
        </div>
      )}
    </div>
  );
}

function PlanRow({ plan, onSaved }: { plan: StorePlan; onSaved: () => void }) {
  const [name, setName] = useState(plan.name);
  const [price, setPrice] = useState((plan.price_cents / 100).toFixed(2));
  const [limit, setLimit] = useState(String(plan.product_limit));
  const [days, setDays] = useState(String(plan.duration_days));
  const save = useMutation({
    mutationFn: (patch: Parameters<typeof adminStores.updatePlan>[1]) => adminStores.updatePlan(plan.id, patch),
    onSuccess: onSaved,
  });
  const priceCents = Math.round(Number(price) * 100);
  const valid = name.trim() && priceCents > 0 && Number(limit) > 0 && Number(days) > 0;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[16px] border border-line bg-surface p-3">
      <input value={name} onChange={(e) => setName(e.target.value)} className={`${inputClass} w-36`} aria-label="Plan name" />
      <label className="flex items-center gap-1 text-[12px] text-muted">
        Price ({plan.currency.toUpperCase()})
        <input type="number" min={0.01} step={0.01} value={price} onChange={(e) => setPrice(e.target.value)} className={`${inputClass} w-24`} />
      </label>
      <label className="flex items-center gap-1 text-[12px] text-muted">
        Products
        <input type="number" min={1} value={limit} onChange={(e) => setLimit(e.target.value)} className={`${inputClass} w-24`} />
      </label>
      <label className="flex items-center gap-1 text-[12px] text-muted">
        Days
        <input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} className={`${inputClass} w-20`} />
      </label>
      <SmallButton
        tone="primary"
        disabled={!valid || save.isPending}
        onClick={() => save.mutate({ name: name.trim(), price_cents: priceCents, product_limit: Number(limit), duration_days: Number(days) })}
      >
        {save.isPending ? "Saving…" : "Save"}
      </SmallButton>
      <SmallButton tone={plan.is_active ? "danger" : "primary"} disabled={save.isPending} onClick={() => save.mutate({ is_active: !plan.is_active })}>
        {plan.is_active ? "Hide plan" : "Offer plan"}
      </SmallButton>
      <span className="text-[12px] text-faint">{money(plan.price_cents, plan.currency)} · {plan.product_limit} products</span>
      {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
    </div>
  );
}
