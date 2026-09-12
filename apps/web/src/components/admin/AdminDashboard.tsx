"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { admin as adminApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const TABS = ["Overview", "Users", "Subscriptions", "Payments", "Retailers"] as const;
type Tab = (typeof TABS)[number];

export function AdminDashboard() {
  const { user, isLoading: sessionLoading } = useSession();
  const [tab, setTab] = useState<Tab>("Overview");

  if (sessionLoading) {
    return (
      <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  if (!user || !user.is_admin) {
    return (
      <section className="mx-auto w-[min(680px,calc(100%-42px))] py-24 text-center">
        <p className="font-display text-[20px] text-ink">Not authorized</p>
        <p className="mt-2 text-[14px] text-muted">This page is for TryOnU admins only.</p>
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-14 md:py-20">
      <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
        Admin <em>dashboard</em>
      </h1>

      <div className="mt-6 flex flex-wrap gap-2 border-b border-line pb-3">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors ${
              tab === t ? "bg-sage text-white" : "text-ink-soft hover:bg-paper-2"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-8">
        {tab === "Overview" && <OverviewTab />}
        {tab === "Users" && <UsersTab />}
        {tab === "Subscriptions" && <SubscriptionsTab />}
        {tab === "Payments" && <PaymentsTab />}
        {tab === "Retailers" && <RetailersTab />}
      </div>
    </section>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[16px] border border-line bg-surface p-4">
      <p className="text-[11px] uppercase tracking-[0.08em] text-faint">{label}</p>
      <p className="mt-1 font-display text-[22px] text-ink">{value}</p>
    </div>
  );
}

function OverviewTab() {
  const query = useQuery({ queryKey: ["admin-overview"], queryFn: adminApi.overview });

  if (query.isLoading) return <TableSkeleton />;
  if (!query.data) return <p className="text-[13px] text-muted">Couldn't load overview.</p>;

  const d = query.data;
  const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total users" value={d.total_users} />
        <StatTile label="New users (7d)" value={d.new_users_7d} />
        <StatTile label="Active subscriptions" value={d.active_subscriptions} />
        <StatTile label="Credits outstanding" value={d.total_credits_outstanding} />
        <StatTile label="Try-ons total" value={d.tryon_jobs_total} />
        <StatTile label="Try-ons (24h)" value={d.tryon_jobs_24h} />
        <StatTile label="Try-on failures (24h)" value={d.tryon_jobs_failed_24h} />
        <StatTile label="Active products" value={d.total_products} />
        <StatTile label="Active retailers" value={d.active_retailers} />
        <StatTile label="Affiliate clicks (7d)" value={d.affiliate_clicks_7d} />
        <StatTile label="AI calls (30d)" value={d.ai_calls_30d} />
        <StatTile label="AI cost (30d)" value={`$${(d.ai_cost_usd_cents_30d / 100).toFixed(2)}`} />
      </div>

      <div>
        <h2 className="font-display text-[16px] text-ink">Revenue (30 days)</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatTile label="Total" value={money(d.revenue_cents_30d)} />
          <StatTile label="Subscriptions" value={money(d.revenue_cents_subscriptions_30d)} />
          <StatTile label="One-off purchases" value={money(d.revenue_cents_one_off_30d)} />
        </div>
      </div>

      <div>
        <h2 className="font-display text-[16px] text-ink">Try-on jobs by status</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(d.tryon_jobs_by_status).map(([status, count]) => (
            <span key={status} className="rounded-full border border-line px-3 py-1 text-[12px] text-ink-soft">
              {status}: <b className="text-ink">{count}</b>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function UsersTab() {
  const query = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.users(50, 0) });
  if (query.isLoading) return <TableSkeleton />;
  if (!query.data) return <p className="text-[13px] text-muted">Couldn't load users.</p>;

  return (
    <Table
      columns={["Email", "Verified", "Admin", "Credits", "Joined"]}
      rows={query.data.items.map((u) => [
        u.email,
        u.email_verified ? "Yes" : "No",
        u.is_admin ? "Yes" : "No",
        u.credits_balance,
        new Date(u.created_at).toLocaleDateString(),
      ])}
    />
  );
}

function SubscriptionsTab() {
  const query = useQuery({ queryKey: ["admin-subscriptions"], queryFn: adminApi.subscriptions });
  if (query.isLoading) return <TableSkeleton />;
  if (!query.data) return <p className="text-[13px] text-muted">Couldn't load subscriptions.</p>;

  return (
    <Table
      columns={["Plan", "Status", "Credits/cycle", "Renews", "Cancels at period end"]}
      rows={query.data.map((s) => [
        String(s.plan),
        String(s.status),
        String(s.credits_per_cycle),
        new Date(String(s.current_period_end)).toLocaleDateString(),
        s.cancel_at_period_end ? "Yes" : "No",
      ])}
    />
  );
}

function PaymentsTab() {
  const query = useQuery({ queryKey: ["admin-payments"], queryFn: adminApi.payments });
  if (query.isLoading) return <TableSkeleton />;
  if (!query.data) return <p className="text-[13px] text-muted">Couldn't load payments.</p>;

  return (
    <Table
      columns={["Amount", "Status", "Provider", "Date"]}
      rows={query.data.map((p) => [
        `${(Number(p.amount_cents) / 100).toFixed(2)} ${String(p.currency).toUpperCase()}`,
        String(p.status),
        String(p.provider),
        new Date(String(p.created_at)).toLocaleDateString(),
      ])}
    />
  );
}

function RetailersTab() {
  const query = useQuery({ queryKey: ["admin-retailers"], queryFn: adminApi.retailers });
  if (query.isLoading) return <TableSkeleton />;
  if (!query.data) return <p className="text-[13px] text-muted">Couldn't load retailers.</p>;

  return (
    <Table
      columns={["Name", "Active", "Affiliate network", "Commission %"]}
      rows={query.data.map((r) => [
        String(r.name),
        r.is_active ? "Yes" : "No",
        r.affiliate_network ? String(r.affiliate_network) : "—",
        r.base_commission_pct != null ? String(r.base_commission_pct) : "—",
      ])}
    />
  );
}

function Table({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  if (rows.length === 0) {
    return <p className="text-[13px] text-muted">No rows yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-[16px] border border-line">
      <table className="w-full min-w-[560px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-line bg-paper-2">
            {columns.map((c) => (
              <th key={c} className="px-4 py-2.5 font-medium text-ink-soft">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2.5 text-ink">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-[10px] bg-paper-2" />
      ))}
    </div>
  );
}
