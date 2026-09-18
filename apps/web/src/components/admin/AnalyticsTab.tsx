"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { admin as adminApi } from "@/lib/api/endpoints";
import type { AnalyticsBreakdown, AnalyticsReport } from "@/lib/api/types";
import { ErrorNote, SectionHeader, StatTile, Table, TableSkeleton, errorText } from "./ui";

const RANGES = [
  { days: 1, label: "Today" },
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
] as const;

const nf = new Intl.NumberFormat("en-US");
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const regionNames = typeof Intl.DisplayNames === "function" ? new Intl.DisplayNames(["en"], { type: "region" }) : null;

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  const total = Math.round(ms / 1000);
  if (total < 60) return `${total}s`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m < 60 ? `${m}m ${s.toString().padStart(2, "0")}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

function countryLabel(code: string): { flag: string; name: string } {
  if (code.length !== 2) return { flag: "🌐", name: "Unknown" };
  const flag = String.fromCodePoint(...[...code.toUpperCase()].map((c) => 127397 + c.charCodeAt(0)));
  let name = code;
  try {
    name = regionNames?.of(code.toUpperCase()) ?? code;
  } catch {
    // unrecognised code: fall back to the raw ISO code
  }
  return { flag, name };
}

const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

export function AnalyticsTab() {
  const [days, setDays] = useState<number>(7);
  const query = useQuery({
    queryKey: ["admin", "analytics", days],
    queryFn: () => adminApi.analytics(days),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });

  return (
    <div>
      <SectionHeader
        title="Visitor analytics"
        hint="Visits to the public site — admin pages, bots and visitors with Do Not Track enabled aren't counted."
      />

      <div className="mb-5 flex flex-wrap items-center gap-1.5" role="group" aria-label="Date range">
        {RANGES.map((r) => (
          <button
            key={r.days}
            type="button"
            aria-pressed={days === r.days}
            onClick={() => setDays(r.days)}
            className={`tu-press h-8 rounded-full px-3.5 text-[12.5px] ${
              days === r.days ? "bg-ink text-paper" : "border border-line text-ink-soft hover:border-line-strong hover:text-ink"
            }`}
          >
            {r.label}
          </button>
        ))}
        <span className="ml-auto text-[11.5px] text-faint">Days are in UTC · refreshes every minute</span>
      </div>

      {query.isLoading ? (
        <TableSkeleton />
      ) : query.isError || !query.data ? (
        <ErrorNote>{errorText(query.error, "Couldn't load analytics.")}</ErrorNote>
      ) : (
        <div className={`tu-stagger space-y-6 transition-opacity ${query.isFetching && query.isPlaceholderData ? "opacity-60" : ""}`}>
          <Report key={query.data.days} data={query.data} />
        </div>
      )}
    </div>
  );
}

function Report({ data }: { data: AnalyticsReport }) {
  return (
    <>
      {!data.geoip_available && (
        <p className="rounded-[14px] border border-[#c9a13b]/40 bg-[#c9a13b]/10 px-4 py-3 text-[12.5px] text-[#8a6d1f]">
          Country lookup isn&rsquo;t available yet, so countries show as Unknown. The server downloads the free
          database automatically on startup — or run <code>python -m app.scripts.update_geoip</code> in{" "}
          <code>apps/api</code> and restart the API.
        </p>
      )}

      <div className="tu-stagger grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Visitors" value={nf.format(data.visitors)} />
        <StatTile label="Page views" value={nf.format(data.views)} />
        <StatTile label="Avg. time on page" value={formatDuration(data.avg_duration_ms)} />
        <StatTile label="Bounce rate" value={data.bounce_rate === null ? "—" : `${Math.round(data.bounce_rate * 100)}%`} />
        <StatTile label="Pages / visit" value={data.pages_per_session ?? "—"} />
        <StatTile
          label="Live now"
          value={
            <span className="inline-flex items-center gap-2">
              {data.live_visitors > 0 && (
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--color-chart)] opacity-60" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--color-chart)]" />
                </span>
              )}
              {nf.format(data.live_visitors)}
            </span>
          }
        />
      </div>

      <Card title="Daily visitors" subtitle={`${nf.format(data.signed_in_visitors)} of them signed in`}>
        <TrendChart daily={data.daily} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Countries" subtitle="Unique visitors by country">
          <BarList
            rows={data.countries}
            total={data.visitors}
            label={(key) => {
              const c = countryLabel(key);
              return (
                <>
                  <span aria-hidden="true" className="mr-2">{c.flag}</span>
                  {c.name}
                </>
              );
            }}
            empty="No visits in this period."
          />
        </Card>
        <Card title="Traffic sources" subtitle="Sites that sent visitors (direct visits aren't listed)">
          <BarList rows={data.referrers} total={data.visitors} label={(k) => k} empty="No external referrals yet." />
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card title="Devices">
          <BarList rows={data.devices} total={data.visitors} label={(k) => k.charAt(0).toUpperCase() + k.slice(1)} empty="—" />
        </Card>
        <Card title="Browsers">
          <BarList rows={data.browsers} total={data.visitors} label={(k) => k} empty="—" />
        </Card>
        <Card title="Operating systems">
          <BarList rows={data.operating_systems} total={data.visitors} label={(k) => k} empty="—" />
        </Card>
      </div>

      <Card title="Pages" subtitle="Most viewed, with how long visitors stayed">
        <Table
          columns={["Page", "Views", "Visitors", "Avg. time on page"]}
          rows={data.pages.map((p) => [
            <code key="p" className="break-all text-[12.5px]">{p.path}</code>,
            nf.format(p.views),
            nf.format(p.visitors),
            formatDuration(p.avg_duration_ms),
          ])}
          empty="No page views in this period."
        />
      </Card>

      {/* required by the database's CC BY 4.0 license */}
      <p className="text-[11px] text-faint">
        Country data:{" "}
        <a href="https://db-ip.com" target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
          IP Geolocation by DB-IP
        </a>
        , licensed under CC BY 4.0.
      </p>
    </>
  );
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[20px] border border-line bg-surface p-5">
      <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
      {subtitle && <p className="mt-0.5 text-[12px] text-muted">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function BarList({
  rows,
  total,
  label,
  empty,
  limit = 8,
}: {
  rows: AnalyticsBreakdown[];
  total: number;
  label: (key: string) => React.ReactNode;
  empty: string;
  limit?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  if (rows.length === 0) return <p className="text-[13px] text-muted">{empty}</p>;
  const max = Math.max(...rows.map((r) => r.visitors), 1);
  const shown = expanded ? rows : rows.slice(0, limit);

  return (
    <div>
      <ul className="space-y-3">
        {shown.map((r) => {
          const share = total ? Math.round((r.visitors / total) * 100) : 0;
          return (
            <li key={r.key}>
              <div className="flex items-baseline justify-between gap-3 text-[13px]">
                <span className="min-w-0 truncate text-ink">{label(r.key)}</span>
                <span className="shrink-0 tabular-nums text-ink-soft">
                  {nf.format(r.visitors)} <span className="text-faint">· {share}%</span>
                </span>
              </div>
              <div
                className="mt-1.5 h-2 rounded-full bg-paper-2"
                title={`${nf.format(r.visitors)} visitors, ${nf.format(r.views)} page views`}
              >
                <div
                  className="tu-bar h-2 rounded-r-full bg-[var(--color-chart)]"
                  style={{ width: `${Math.max((r.visitors / max) * 100, 1.5)}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
      {rows.length > limit && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="tu-press mt-3 text-[12px] text-sage-deep hover:underline"
        >
          {expanded ? "Show less" : `Show all ${rows.length}`}
        </button>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ trend chart

const CHART_H = 220;
const PAD = { top: 12, right: 12, bottom: 28, left: 40 };

function niceMax(value: number): number {
  if (value <= 4) return 4;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s * 4 >= value) ?? magnitude * 10;
  return step * 4;
}

function TrendChart({ daily }: { daily: AnalyticsReport["daily"] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(260, Math.round(entry.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const geometry = useMemo(() => {
    const innerW = width - PAD.left - PAD.right;
    const innerH = CHART_H - PAD.top - PAD.bottom;
    const yMax = niceMax(Math.max(...daily.map((d) => d.visitors), 0));
    const x = (i: number) => PAD.left + (daily.length === 1 ? innerW / 2 : (i / (daily.length - 1)) * innerW);
    const y = (v: number) => PAD.top + innerH - (v / yMax) * innerH;
    const ticks = [0, 1, 2, 3, 4].map((k) => (yMax / 4) * k);
    const line = daily.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.visitors).toFixed(1)}`).join("");
    const area = daily.length > 1 ? `${line}L${x(daily.length - 1)},${y(0)}L${x(0)},${y(0)}Z` : "";
    const labelEvery = Math.max(1, Math.ceil(daily.length / Math.max(2, Math.floor(innerW / 64))));
    return { innerW, x, y, ticks, line, area, labelEvery };
  }, [daily, width]);

  const total = daily.reduce((sum, d) => sum + d.views, 0);
  if (total === 0) {
    return <p className="py-10 text-center text-[13px] text-muted">No visits recorded in this period yet.</p>;
  }

  const indexFromPointer = (e: PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = (e.clientX - rect.left) / rect.width;
    return Math.min(daily.length - 1, Math.max(0, Math.round(rel * (daily.length - 1))));
  };

  const onKey = (e: KeyboardEvent<SVGRectElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    setActive((cur) => {
      const start = cur ?? daily.length - 1;
      return Math.min(daily.length - 1, Math.max(0, start + (e.key === "ArrowRight" ? 1 : -1)));
    });
  };

  const point = active !== null ? daily[active] : null;
  const tipLeft = active !== null ? geometry.x(active) : 0;

  return (
    <div>
      <div ref={wrapRef} className="relative">
        <svg width={width} height={CHART_H} role="img" aria-label="Daily unique visitors" className="block overflow-visible">
          {geometry.ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={geometry.y(t)} y2={geometry.y(t)} stroke="var(--color-line)" strokeWidth={1} />
              <text x={PAD.left - 8} y={geometry.y(t)} textAnchor="end" dominantBaseline="middle" fontSize={11} fill="var(--color-faint)">
                {compact.format(t)}
              </text>
            </g>
          ))}
          {daily.map((d, i) =>
            // counted back from today so the most recent day is always labelled without colliding
            (daily.length - 1 - i) % geometry.labelEvery === 0 ? (
              <text key={d.date} x={geometry.x(i)} y={CHART_H - 8} textAnchor="middle" fontSize={11} fill="var(--color-faint)">
                {shortDate(d.date)}
              </text>
            ) : null,
          )}
          {geometry.area && <path d={geometry.area} fill="var(--color-chart)" opacity={0.1} className="tu-fade" />}
          {daily.length > 1 && (
            <path d={geometry.line} pathLength={1} className="tu-line-draw" fill="none" stroke="var(--color-chart)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          )}
          {daily.length === 1 && (
            <circle cx={geometry.x(0)} cy={geometry.y(daily[0].visitors)} r={4} fill="var(--color-chart)" stroke="var(--color-surface)" strokeWidth={2} />
          )}
          {point && active !== null && (
            <>
              <line x1={tipLeft} x2={tipLeft} y1={PAD.top} y2={CHART_H - PAD.bottom} stroke="var(--color-line-strong)" strokeWidth={1} />
              <circle cx={tipLeft} cy={geometry.y(point.visitors)} r={4.5} fill="var(--color-chart)" stroke="var(--color-surface)" strokeWidth={2} />
            </>
          )}
          <rect
            x={PAD.left}
            y={PAD.top}
            width={Math.max(geometry.innerW, 1)}
            height={CHART_H - PAD.top - PAD.bottom}
            fill="transparent"
            tabIndex={0}
            aria-label="Chart data — use left and right arrow keys to read each day"
            onPointerMove={(e) => setActive(indexFromPointer(e))}
            onPointerLeave={() => setActive(null)}
            onFocus={() => setActive((cur) => cur ?? daily.length - 1)}
            onBlur={() => setActive(null)}
            onKeyDown={onKey}
            className="cursor-crosshair outline-none focus-visible:stroke-[var(--color-line-strong)]"
          />
        </svg>

        {point && active !== null && (
          <div
            role="status"
            className="pointer-events-none absolute top-1 z-10 min-w-[150px] rounded-[12px] border border-line bg-surface px-3 py-2 text-[12px] shadow-lift"
            style={
              tipLeft > width / 2
                ? { right: width - tipLeft + 12 }
                : { left: tipLeft + 12 }
            }
          >
            <p className="text-faint">{shortDate(point.date)}</p>
            <p className="mt-1 flex items-center gap-2">
              <span className="h-0.5 w-3 rounded bg-[var(--color-chart)]" aria-hidden="true" />
              <b className="text-[14px] text-ink">{nf.format(point.visitors)}</b>
              <span className="text-ink-soft">visitors</span>
            </p>
            <p className="mt-0.5 pl-5">
              <b className="text-ink">{nf.format(point.views)}</b> <span className="text-ink-soft">page views</span>
            </p>
          </div>
        )}
      </div>

      <details className="mt-3">
        <summary className="cursor-pointer text-[12px] text-muted hover:text-ink">View as table</summary>
        <div className="mt-2">
          <Table
            columns={["Date", "Visitors", "Page views"]}
            rows={[...daily].reverse().map((d) => [shortDate(d.date), nf.format(d.visitors), nf.format(d.views)])}
          />
        </div>
      </details>
    </div>
  );
}
