"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminStores } from "@/lib/api/endpoints";
import type { AdminStore, AdminStoreDetail, StorePlan } from "@/lib/api/types";
import { countryName } from "@/lib/countries";
import { Badge, ErrorNote, SectionHeader, SmallButton, StatTile, Table, TableSkeleton, errorText, inputClass, money } from "./ui";

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
  const [openId, setOpenId] = useState<string | null>(null);
  const summary = useQuery({ queryKey: ["admin", "stores", "summary"], queryFn: adminStores.summary });
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

  const revenue = summary.data
    ? Object.entries(summary.data.plan_revenue).map(([cur, cents]) => money(cents, cur)).join(" + ") || money(0, "usd")
    : "—";
  return (
    <div className="space-y-10">
      {summary.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <StatTile label="Waiting for approval" value={summary.data.by_status.pending ?? 0} tone={(summary.data.by_status.pending ?? 0) > 0 ? "warn" : undefined} />
          <StatTile label="Approved stores" value={summary.data.by_status.approved ?? 0} />
          <StatTile label="Live now" value={summary.data.live} />
          <StatTile label="Products on sale" value={summary.data.products.toLocaleString()} />
          <StatTile label="Plan revenue" value={revenue} />
        </div>
      )}
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
                <SmallButton onClick={() => setOpenId(openId === s.id ? null : s.id)}>{openId === s.id ? "Close" : "Details"}</SmallButton>
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
        {openId && <StoreDetail id={openId} onClose={() => setOpenId(null)} />}
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


function StoreDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["admin", "store", id], queryFn: () => adminStores.detail(id) });
  const plans = useQuery({ queryKey: ["admin", "store-plans"], queryFn: adminStores.plans });
  const [planCode, setPlanCode] = useState("");
  const [days, setDays] = useState("30");
  const update = (d: AdminStoreDetail) => {
    qc.setQueryData(["admin", "store", id], d);
    qc.invalidateQueries({ queryKey: ["admin", "stores"] });
  };
  const grant = useMutation({ mutationFn: () => adminStores.grantPlan(id, planCode, Number(days)), onSuccess: update });
  const toggle = useMutation({
    mutationFn: ({ productId, active }: { productId: string; active: boolean }) => adminStores.setProductActive(id, productId, active),
    onSuccess: update,
  });
  const remove = useMutation({ mutationFn: (productId: string) => adminStores.deleteProduct(id, productId), onSuccess: update });

  if (detail.isLoading) return <div className="mt-4"><TableSkeleton /></div>;
  if (detail.isError || !detail.data) return <div className="mt-4"><ErrorNote>{errorText(detail.error, "Couldn't load this store.")}</ErrorNote></div>;
  const d = detail.data;
  return (
    <div className="mt-5 space-y-5 rounded-[20px] border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display text-[20px] text-ink">{d.name}</p>
          <p className="text-[12.5px] text-muted">
            {countryName(d.country)} · owner {d.owner_email} · contact {d.contact_email ?? "—"} · opened {new Date(d.created_at).toLocaleDateString()}
          </p>
          {d.description && <p className="mt-2 max-w-2xl text-[13px] text-ink-soft">{d.description}</p>}
        </div>
        <div className="flex gap-1.5">
          {d.live && (
            <a href={`/stores/${d.slug}`} target="_blank" rel="noopener" className="text-[12.5px] font-medium text-sage-deep hover:underline">
              Public page ↗
            </a>
          )}
          <SmallButton onClick={onClose}>Close</SmallButton>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Plan" value={d.plan_active ? `${d.plan_code} · until ${new Date(d.plan_expires_at!).toLocaleDateString()}` : "None"} />
        <StatTile label="Products" value={`${d.product_count} / ${d.plan_active ? d.plan_product_limit : 0}`} />
        <StatTile label={`Shop clicks · ${d.stats.days}d`} value={d.stats.clicks} />
        <StatTile label={`Try-ons · ${d.stats.days}d`} value={d.stats.tryons} />
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-[16px] border border-line p-3">
        <span className="text-[13px] font-medium text-ink">Give or extend a plan without payment:</span>
        <select value={planCode} onChange={(e) => setPlanCode(e.target.value)} className={`${inputClass} w-40`}>
          <option value="">Choose a plan</option>
          {plans.data?.map((p: StorePlan) => (
            <option key={p.id} value={p.code}>{p.name} ({p.product_limit} products)</option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-[12px] text-muted">
          Days
          <input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} className={`${inputClass} w-20`} />
        </label>
        <SmallButton tone="primary" disabled={!planCode || Number(days) < 1 || grant.isPending} onClick={() => grant.mutate()}>
          {grant.isPending ? "Saving…" : "Apply"}
        </SmallButton>
        {grant.isError && <ErrorNote>{errorText(grant.error)}</ErrorNote>}
      </div>

      <div>
        <p className="text-[13px] font-semibold text-ink">Payments</p>
        {d.payments.length === 0 ? (
          <p className="mt-1 text-[12.5px] text-muted">No payments yet.</p>
        ) : (
          <div className="mt-2 divide-y divide-line rounded-[14px] border border-line">
            {d.payments.map((p) => (
              <div key={p.id} className="flex items-center justify-between gap-3 px-3 py-2 text-[12.5px]">
                <span className="text-ink-soft">{p.plan_name ?? "Plan"} · {new Date(p.created_at).toLocaleString()}</span>
                <span className="flex items-center gap-2">
                  {money(p.amount_cents, p.currency)}
                  <Badge tone={p.status === "succeeded" ? "good" : p.status === "failed" ? "bad" : "neutral"}>{p.status}</Badge>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <p className="text-[13px] font-semibold text-ink">Products ({d.products.length})</p>
        {(toggle.isError || remove.isError) && <div className="mt-2"><ErrorNote>{errorText(toggle.error ?? remove.error)}</ErrorNote></div>}
        {d.products.length === 0 ? (
          <p className="mt-1 text-[12.5px] text-muted">No products yet.</p>
        ) : (
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {d.products.map((p) => (
              <div key={p.id} className={`flex flex-col overflow-hidden rounded-[14px] border bg-surface ${p.is_active ? "border-line" : "border-dashed border-line opacity-60"}`}>
                <div className="aspect-[4/5] bg-white">
                  {p.images[0] ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.images[0]} alt={p.name} className="h-full w-full object-contain p-1.5" />
                  ) : (
                    <div className="grid h-full place-items-center text-[11px] text-faint">No photo</div>
                  )}
                </div>
                <div className="flex flex-1 flex-col p-2">
                  <a href={p.product_url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 text-[11.5px] leading-snug text-ink hover:underline">
                    {p.name}
                  </a>
                  <p className="mt-1 text-[12px] font-semibold text-ink">{money(p.price_cents, p.currency)}</p>
                  <div className="mt-auto flex flex-wrap gap-1 pt-2">
                    <SmallButton disabled={toggle.isPending} onClick={() => toggle.mutate({ productId: p.id, active: !p.is_active })}>
                      {p.is_active ? "Hide" : "Show"}
                    </SmallButton>
                    <SmallButton tone="danger" disabled={remove.isPending} onClick={() => remove.mutate(p.id)}>
                      Delete
                    </SmallButton>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
