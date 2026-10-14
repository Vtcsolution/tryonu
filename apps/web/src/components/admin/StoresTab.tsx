"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminStores } from "@/lib/api/endpoints";
import type { AdminStore, AdminStoreDetail, StorePlan } from "@/lib/api/types";
import { countryName } from "@/lib/countries";
import { Badge, ErrorNote, SectionHeader, SmallButton, StatTile, Table, TableSkeleton, errorText, inputClass, money } from "./ui";

const FILTERS: [string, string][] = [
  ["", "All stores"],
  ["pending", "Waiting"],
  ["approved", "Approved"],
  ["suspended", "Suspended"],
  ["rejected", "Rejected"],
];

const DAY = 86_400_000;
const planName = (code: string | null) => (code ? code.replace(/^./, (c) => c.toUpperCase()) : "No plan");
const daysLeft = (iso: string | null) => (iso ? Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / DAY)) : 0);

/** "Basic" with a Paid / Free tag, or "No plan". */
function PlanCell({ s }: { s: AdminStore }) {
  if (!s.plan_active) return <span className="text-muted">No plan</span>;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <span className="font-medium text-ink">{planName(s.plan_code)}</span>
      <Badge tone={s.plan_free ? "warn" : "good"}>{s.plan_free ? "Free" : "Paid"}</Badge>
    </span>
  );
}

function EndsCell({ s }: { s: AdminStore }) {
  if (!s.plan_active || !s.plan_expires_at) return <span className="text-muted">—</span>;
  const left = daysLeft(s.plan_expires_at);
  return (
    <span>
      {new Date(s.plan_expires_at).toLocaleDateString()}
      <span className={`block text-[11.5px] ${left <= 3 ? "text-[#a4553f]" : "text-muted"}`}>
        {left === 1 ? "1 day left" : `${left} days left`}
      </span>
    </span>
  );
}

/** "12 of 50 used · 38 left" with a small bar. */
function UsageCell({ used, limit }: { used: number; limit: number }) {
  if (limit <= 0) return <span>{used} uploaded<span className="block text-[11.5px] text-muted">no plan limit yet</span></span>;
  const pct = Math.min(100, Math.round((used / limit) * 100));
  return (
    <span className="block min-w-[120px]">
      {used} of {limit.toLocaleString()} used
      <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-paper-2">
        <span className={`block h-full rounded-full ${pct >= 90 ? "bg-[#c0503a]" : "bg-sage"}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="block text-[11.5px] text-muted">{Math.max(0, limit - used).toLocaleString()} left</span>
    </span>
  );
}
const TONE: Record<string, "good" | "bad" | "warn" | "neutral"> = {
  pending: "warn",
  approved: "good",
  rejected: "bad",
  suspended: "bad",
};

/** Company stores: approve new ones, suspend bad ones, and set plan prices. */
export function StoresTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState("");
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
          hint="Every store, its plan and how many products it has used. A store's products reach shoppers only when it is approved AND has a plan (paid, or free from you). Open Details to give a free plan."
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
            columns={["Store", "Owner", "Plan", "Plan ends", "Products", "Status", ""]}
            rows={stores.data.map((s) => [
              <div key="n">
                <p className="font-medium text-ink">{s.name}</p>
                <p className="text-[11.5px] text-muted">{countryName(s.country)}</p>
                {s.website_url && (
                  <a href={s.website_url} target="_blank" rel="noopener noreferrer" className="text-[11.5px] text-sage-deep hover:underline">
                    {s.website_url.replace(/^https?:\/\//, "")}
                  </a>
                )}
              </div>,
              s.owner_email,
              <PlanCell key="p" s={s} />,
              <EndsCell key="e" s={s} />,
              <UsageCell key="u" used={s.product_count} limit={s.plan_active ? s.plan_product_limit : 0} />,
              <Badge key="s" tone={TONE[s.status] ?? "neutral"}>{s.status}</Badge>,
              <div key="a" className="flex flex-wrap gap-1.5">
                <SmallButton onClick={() => setOpenId(openId === s.id ? null : s.id)}>{openId === s.id ? "Close" : "Details & plan"}</SmallButton>
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
  const [featured, setFeatured] = useState(String(plan.featured_limit ?? 0));
  const [days, setDays] = useState(String(plan.duration_days));
  const save = useMutation({
    mutationFn: (patch: Parameters<typeof adminStores.updatePlan>[1]) => adminStores.updatePlan(plan.id, patch),
    onSuccess: onSaved,
  });
  const priceCents = Math.round(Number(price) * 100);
  const valid = name.trim() && priceCents > 0 && Number(limit) > 0 && Number(days) > 0 && Number(featured) >= 0;
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
        ★ Featured
        <input type="number" min={0} value={featured} onChange={(e) => setFeatured(e.target.value)} className={`${inputClass} w-20`} />
      </label>
      <label className="flex items-center gap-1 text-[12px] text-muted">
        Days
        <input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} className={`${inputClass} w-20`} />
      </label>
      <SmallButton
        tone="primary"
        disabled={!valid || save.isPending}
        onClick={() =>
          save.mutate({ name: name.trim(), price_cents: priceCents, product_limit: Number(limit), featured_limit: Number(featured), duration_days: Number(days) })
        }
      >
        {save.isPending ? "Saving…" : "Save"}
      </SmallButton>
      <SmallButton tone={plan.is_active ? "danger" : "primary"} disabled={save.isPending} onClick={() => save.mutate({ is_active: !plan.is_active })}>
        {plan.is_active ? "Hide plan" : "Offer plan"}
      </SmallButton>
      <span className="text-[12px] text-faint">
        {money(plan.price_cents, plan.currency)} · {plan.product_limit} products · ★ {plan.featured_limit ?? 0} featured
      </span>
      {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
    </div>
  );
}


/** Succeeded plan payments, per currency. */
function totalPaid(d: AdminStoreDetail): string {
  const sums: Record<string, number> = {};
  for (const p of d.payments) if (p.status === "succeeded") sums[p.currency] = (sums[p.currency] ?? 0) + p.amount_cents;
  const parts = Object.entries(sums).map(([cur, cents]) => money(cents, cur));
  return parts.length ? parts.join(" + ") : money(0, "usd");
}

function StoreDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["admin", "store", id], queryFn: () => adminStores.detail(id) });
  const plans = useQuery({ queryKey: ["admin", "store-plans"], queryFn: adminStores.plans });
  const [planCode, setPlanCode] = useState("");
  const [days, setDays] = useState("30");
  const [confirmEnd, setConfirmEnd] = useState(false);
  const update = (d: AdminStoreDetail) => {
    qc.setQueryData(["admin", "store", id], d);
    qc.invalidateQueries({ queryKey: ["admin", "stores"] });
  };
  const grant = useMutation({ mutationFn: () => adminStores.grantPlan(id, planCode, Number(days)), onSuccess: update });
  const end = useMutation({
    mutationFn: () => adminStores.endPlan(id),
    onSuccess: (d) => {
      update(d);
      setConfirmEnd(false);
    },
  });
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

      <div>
        <p className="mb-2 text-[13px] font-semibold text-ink">Plan</p>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile
            label="Plan"
            value={
              d.plan_active ? (
                <span className="flex flex-wrap items-center gap-2">
                  {planName(d.plan_code)}
                  <Badge tone={d.plan_free ? "warn" : "good"}>{d.plan_free ? "Free from admin" : "Paid"}</Badge>
                </span>
              ) : (
                "No plan"
              )
            }
          />
          <StatTile
            label="Plan ends"
            value={d.plan_active && d.plan_expires_at ? `${new Date(d.plan_expires_at).toLocaleDateString()} · ${daysLeft(d.plan_expires_at)}d left` : "—"}
          />
          <StatTile label="Auto-renew" value={d.auto_renew ? "On (PayPal)" : d.subscription_status ? `Off · ${d.subscription_status.toLowerCase()}` : "Off"} />
          <StatTile label="Total paid" value={totalPaid(d)} />
        </div>
      </div>

      <div>
        <p className="mb-2 text-[13px] font-semibold text-ink">Products</p>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <StatTile label="Uploaded (on sale)" value={d.product_count} />
          <StatTile label="Hidden" value={d.products.filter((p) => !p.is_active).length} />
          <StatTile label="★ Featured" value={`${d.featured_count ?? 0} of ${d.plan_featured_limit ?? 0}`} />
          <StatTile label="Plan limit" value={d.plan_active ? d.plan_product_limit.toLocaleString() : "—"} />
          <StatTile
            label="Can still add"
            value={d.plan_active ? Math.max(0, d.plan_product_limit - d.product_count).toLocaleString() : "Needs a plan"}
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatTile label={`Views · ${d.stats.days}d`} value={d.stats.views} />
        <StatTile label={`Shop clicks · ${d.stats.days}d`} value={d.stats.clicks} />
        <StatTile label={`Try-ons · ${d.stats.days}d`} value={d.stats.tryons} />
      </div>

      <div className="rounded-[16px] border border-sage/40 bg-sage-tint/20 p-4">
        <p className="text-[14px] font-semibold text-ink">Give a free plan (no payment)</p>
        <p className="mt-0.5 text-[12.5px] text-muted">
          The store gets the plan&apos;s product limit right away. Days are added on top of any time it has left.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select value={planCode} onChange={(e) => setPlanCode(e.target.value)} className={`${inputClass} w-48`} aria-label="Plan">
            <option value="">Choose a plan</option>
            {plans.data?.map((p: StorePlan) => (
              <option key={p.id} value={p.code}>{p.name} ({p.product_limit.toLocaleString()} products)</option>
            ))}
          </select>
          {["7", "30", "90", "365"].map((n) => (
            <SmallButton key={n} tone={days === n ? "primary" : "neutral"} onClick={() => setDays(n)}>
              {n === "365" ? "1 year" : `${n} days`}
            </SmallButton>
          ))}
          <label className="flex items-center gap-1 text-[12px] text-muted">
            or
            <input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} className={`${inputClass} w-20`} aria-label="Days" />
            days
          </label>
          <SmallButton tone="primary" disabled={!planCode || Number(days) < 1 || grant.isPending} onClick={() => grant.mutate()}>
            {grant.isPending ? "Saving…" : "Give free plan"}
          </SmallButton>
        </div>
        {grant.isSuccess && <p className="mt-2 text-[12.5px] font-medium text-sage-deep">✓ Plan given.</p>}
        {grant.isError && <div className="mt-2"><ErrorNote>{errorText(grant.error)}</ErrorNote></div>}

        {d.plan_active && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <span className="text-[12.5px] text-muted">
              Stop this store&apos;s plan now; its products leave search.{d.auto_renew ? " PayPal auto-renew stays on until the owner cancels it." : ""}
            </span>
            {confirmEnd ? (
              <>
                <SmallButton tone="danger" disabled={end.isPending} onClick={() => end.mutate()}>
                  {end.isPending ? "Ending…" : "Yes, end the plan"}
                </SmallButton>
                <SmallButton onClick={() => setConfirmEnd(false)}>Cancel</SmallButton>
              </>
            ) : (
              <SmallButton tone="danger" onClick={() => setConfirmEnd(true)}>End plan now</SmallButton>
            )}
            {end.isError && <ErrorNote>{errorText(end.error)}</ErrorNote>}
          </div>
        )}
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
