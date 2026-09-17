"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { admin as adminApi } from "@/lib/api/endpoints";
import {
  Badge,
  ErrorNote,
  PAGE_SIZE,
  Pager,
  SectionHeader,
  SimplePager,
  StatTile,
  Table,
  TableSkeleton,
  errorText,
  money,
  when,
} from "./ui";

export function OverviewTab() {
  const query = useQuery({ queryKey: ["admin", "overview"], queryFn: adminApi.overview });
  if (query.isLoading) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorNote>{errorText(query.error, "Couldn't load overview.")}</ErrorNote>;

  const d = query.data;
  const failRate = d.tryon_jobs_24h ? Math.round((d.tryon_jobs_failed_24h / d.tryon_jobs_24h) * 100) : 0;

  return (
    <div className="space-y-8">
      <SectionHeader title="Overview" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total users" value={d.total_users} />
        <StatTile label="New users (7d)" value={d.new_users_7d} />
        <StatTile label="Active subscriptions" value={d.active_subscriptions} />
        <StatTile label="Credits outstanding" value={d.total_credits_outstanding} />
        <StatTile label="Try-ons total" value={d.tryon_jobs_total} />
        <StatTile label="Try-ons (24h)" value={d.tryon_jobs_24h} />
        <StatTile
          label="Try-on failures (24h)"
          value={`${d.tryon_jobs_failed_24h}${d.tryon_jobs_24h ? ` · ${failRate}%` : ""}`}
          tone={failRate >= 20 ? "warn" : undefined}
        />
        <StatTile label="Saved products" value={d.total_products} />
        <StatTile label="Active retailers" value={d.active_retailers} />
        <StatTile label="Shop clicks (7d)" value={d.affiliate_clicks_7d} />
        <StatTile label="AI calls (30d)" value={d.ai_calls_30d} />
        <StatTile label="AI cost (30d)" value={`$${(d.ai_cost_usd_cents_30d / 100).toFixed(2)}`} />
      </div>

      <div>
        <h3 className="font-display text-[16px] text-ink">Revenue</h3>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="All time" value={money(d.revenue_cents_total)} />
          <StatTile label="Last 30 days" value={money(d.revenue_cents_30d)} />
          <StatTile label="Subscriptions (30d)" value={money(d.revenue_cents_subscriptions_30d)} />
          <StatTile label="Credit packs (30d)" value={money(d.revenue_cents_one_off_30d)} />
        </div>
      </div>

      <div>
        <h3 className="font-display text-[16px] text-ink">Try-on jobs by status</h3>
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

export function SystemTab() {
  const query = useQuery({ queryKey: ["admin", "system"], queryFn: adminApi.system });
  if (query.isLoading) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorNote>{errorText(query.error, "Couldn't load system status.")}</ErrorNote>;
  const s = query.data;

  const live = (value: string, mockLabel = "mock") =>
    value === mockLabel ? <Badge tone="bad">{value} (not live)</Badge> : <Badge tone="good">{value}</Badge>;

  return (
    <div>
      <SectionHeader
        title="System"
        hint="What the running server is actually configured with. Values come from the server's .env — change them there and restart."
      />
      <Table
        columns={["Setting", "Value"]}
        rows={[
          ["Environment", <Badge key="e" tone={s.env === "production" ? "good" : "warn"}>{s.env}</Badge>],
          ["Try-on provider", live(s.tryon_provider)],
          [
            "FASHN model",
            <Badge key="f" tone={s.fashn_model === "tryon-max" ? "good" : "warn"}>
              {s.fashn_model}
              {s.fashn_model !== "tryon-max" ? " — shoes won't render, lower quality" : ""}
            </Badge>,
          ],
          ["AI stylist (LLM)", live(s.llm_provider)],
          ["Payments", live(s.payment_provider)],
          ["Email", live(s.email_provider)],
          ["File storage", s.storage],
          ["Job queue", s.job_queue],
          ["Signup free credits", s.signup_free_credits],
          ["Single try-on cost", `${s.tryon_credit_cost} credits`],
          ["Outfit try-on cost", `${s.outfit_tryon_credit_cost} credits`],
        ]}
      />
    </div>
  );
}

export function PaymentsTab() {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["admin", "payments", offset],
    queryFn: () => adminApi.payments({ limit: PAGE_SIZE, offset }),
  });
  if (query.isLoading) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorNote>{errorText(query.error, "Couldn't load payments.")}</ErrorNote>;

  return (
    <div>
      <SectionHeader title="Payments" />
      <Table
        columns={["Amount", "Status", "Provider", "Reference", "Date"]}
        rows={query.data.map((p) => [
          money(Number(p.amount_cents), String(p.currency)),
          <Badge key="s" tone={p.status === "succeeded" ? "good" : p.status === "failed" ? "bad" : "neutral"}>
            {String(p.status)}
          </Badge>,
          String(p.provider),
          <span key="r" className="text-[11px] text-faint">{String(p.external_payment_id ?? "—")}</span>,
          when(String(p.created_at)),
        ])}
        empty="No payments yet."
      />
      <SimplePager offset={offset} count={query.data.length} onChange={setOffset} />
    </div>
  );
}

export function SubscriptionsTab() {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["admin", "subscriptions", offset],
    queryFn: () => adminApi.subscriptions({ limit: PAGE_SIZE, offset }),
  });
  if (query.isLoading) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorNote>{errorText(query.error, "Couldn't load subscriptions.")}</ErrorNote>;

  return (
    <div>
      <SectionHeader title="Subscriptions" />
      <Table
        columns={["Plan", "Status", "Credits / cycle", "Renews", "Cancels at period end"]}
        rows={query.data.map((s) => [
          String(s.plan),
          <Badge key="s" tone={s.status === "active" ? "good" : s.status === "past_due" ? "bad" : "neutral"}>
            {String(s.status)}
          </Badge>,
          String(s.credits_per_cycle),
          when(String(s.current_period_end)),
          s.cancel_at_period_end ? "Yes" : "No",
        ])}
        empty="No subscriptions yet."
      />
      <SimplePager offset={offset} count={query.data.length} onChange={setOffset} />
    </div>
  );
}

export function AffiliateClicksTab() {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["admin", "affiliate-clicks", offset],
    queryFn: () => adminApi.affiliateClicks({ limit: PAGE_SIZE, offset }),
  });
  if (query.isLoading) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorNote>{errorText(query.error, "Couldn't load clicks.")}</ErrorNote>;

  return (
    <div>
      <SectionHeader
        title="Shop clicks"
        hint="Every “Shop now” click sent to a retailer. Commission is only earned where that retailer's tracking is configured (see Retailers)."
      />
      <Table
        columns={["When", "Product", "Retailer", "User", "Source"]}
        rows={query.data.map((c) => [
          when(c.created_at),
          <span key="p" className="line-clamp-2 max-w-[300px]">{c.product_name ?? c.product_id}</span>,
          c.retailer_name ?? "—",
          c.user_email ?? "Guest",
          c.source.replaceAll("_", " "),
        ])}
        empty="No shop clicks yet."
      />
      <SimplePager offset={offset} count={query.data.length} onChange={setOffset} />
    </div>
  );
}

export function AIUsageTab() {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["admin", "ai-usage", offset],
    queryFn: () => adminApi.aiUsage({ limit: PAGE_SIZE, offset }),
  });
  if (query.isLoading) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorNote>{errorText(query.error, "Couldn't load AI usage.")}</ErrorNote>;

  return (
    <div>
      <SectionHeader title="AI usage" hint="Every call to FASHN (try-on) and the LLM (stylist), including failures." />
      <Table
        columns={["When", "Kind", "Provider", "Model", "Result", "Latency", "Cost"]}
        rows={query.data.map((u) => [
          when(u.created_at),
          u.kind.replaceAll("_", " "),
          u.provider,
          u.model,
          u.success ? <Badge key="s" tone="good">ok</Badge> : <Badge key="s" tone="bad">failed</Badge>,
          u.latency_ms != null ? `${(u.latency_ms / 1000).toFixed(1)}s` : "—",
          u.cost_usd_cents != null ? `$${(u.cost_usd_cents / 100).toFixed(3)}` : "—",
        ])}
        empty="No AI calls yet."
      />
      <SimplePager offset={offset} count={query.data.length} onChange={setOffset} />
    </div>
  );
}

export function AuditLogTab() {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["admin", "audit", offset],
    queryFn: () => adminApi.auditLog({ limit: PAGE_SIZE, offset }),
  });
  if (query.isLoading) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorNote>{errorText(query.error, "Couldn't load the audit log.")}</ErrorNote>;

  return (
    <div>
      <SectionHeader title="Audit log" hint="Every change made from this panel, and by whom." />
      <Table
        columns={["When", "Admin", "Action", "Target", "Details"]}
        rows={query.data.items.map((e) => [
          when(e.created_at),
          e.admin_email ?? "—",
          <Badge key="a">{e.action}</Badge>,
          <span key="t" className="text-[12px]">
            {e.target_type} <span className="text-faint">{e.target_id.slice(0, 12)}</span>
          </span>,
          <code key="d" className="line-clamp-2 max-w-[340px] break-all text-[11px] text-muted">
            {e.detail ? JSON.stringify(e.detail) : "—"}
          </code>,
        ])}
        empty="No admin actions recorded yet."
      />
      <Pager offset={offset} total={query.data.total} onChange={setOffset} />
    </div>
  );
}
