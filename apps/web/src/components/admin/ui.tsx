"use client";

import type { ReactNode } from "react";
import { ApiError } from "@/lib/api/client";

export const PAGE_SIZE = 25;

export const money = (cents: number, currency = "usd") =>
  `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`;

export const when = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";

export function errorText(err: unknown, fallback = "Something went wrong."): string {
  return err instanceof ApiError ? err.detail : fallback;
}

export function StatTile({ label, value, tone }: { label: string; value: ReactNode; tone?: "warn" }) {
  return (
    <div className="rounded-[16px] border border-line bg-surface p-4">
      <p className="text-[11px] uppercase tracking-[0.08em] text-faint">{label}</p>
      <p className={`mt-1 font-display text-[22px] ${tone === "warn" ? "text-[#a4553f]" : "text-ink"}`}>{value}</p>
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "good" | "bad" | "warn" | "neutral" }) {
  const tones = {
    good: "border-sage/40 bg-sage-tint/40 text-sage-deep",
    bad: "border-[#c0503a]/30 bg-[#c0503a]/10 text-[#a4553f]",
    warn: "border-[#c9a13b]/40 bg-[#c9a13b]/10 text-[#8a6d1f]",
    neutral: "border-line bg-paper-2 text-ink-soft",
  };
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function SmallButton({
  children,
  onClick,
  disabled,
  tone = "neutral",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "neutral" | "danger" | "primary";
  type?: "button" | "submit";
}) {
  const tones = {
    neutral: "border-line-strong text-ink hover:border-ink/40",
    danger: "border-[#c0503a]/40 text-[#a4553f] hover:bg-[#c0503a]/10",
    primary: "border-sage bg-sage text-white hover:bg-sage-deep",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex h-8 items-center whitespace-nowrap rounded-full border px-3 text-[12px] font-medium transition-colors disabled:opacity-50 ${tones[tone]}`}
    >
      {children}
    </button>
  );
}

export const inputClass =
  "h-9 rounded-full border border-line-strong bg-paper px-3.5 text-[13px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25";

export function Table({ columns, rows, empty = "Nothing here yet." }: { columns: string[]; rows: ReactNode[][]; empty?: string }) {
  if (rows.length === 0) {
    return <p className="rounded-[16px] border border-dashed border-line p-6 text-center text-[13px] text-muted">{empty}</p>;
  }
  return (
    <div className="overflow-x-auto rounded-[16px] border border-line bg-surface">
      <table className="w-full min-w-[640px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-line bg-paper-2">
            {columns.map((c, i) => (
              <th key={i} className="whitespace-nowrap px-4 py-2.5 font-medium text-ink-soft">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-line align-middle last:border-0">
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

export function Pager({
  offset,
  total,
  onChange,
  pageSize = PAGE_SIZE,
}: {
  offset: number;
  total: number;
  onChange: (offset: number) => void;
  pageSize?: number;
}) {
  if (total <= pageSize) return null;
  const page = Math.floor(offset / pageSize) + 1;
  const pages = Math.ceil(total / pageSize);
  return (
    <div className="mt-3 flex items-center justify-end gap-2 text-[12px] text-muted">
      <SmallButton disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - pageSize))}>
        ← Prev
      </SmallButton>
      <span>
        Page {page} of {pages} · {total} total
      </span>
      <SmallButton disabled={page >= pages} onClick={() => onChange(offset + pageSize)}>
        Next →
      </SmallButton>
    </div>
  );
}

// For endpoints that return plain arrays without a total: only "next" if
// the last page came back full.
export function SimplePager({ offset, count, onChange }: { offset: number; count: number; onChange: (o: number) => void }) {
  if (offset === 0 && count < PAGE_SIZE) return null;
  return (
    <div className="mt-3 flex items-center justify-end gap-2">
      <SmallButton disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - PAGE_SIZE))}>
        ← Prev
      </SmallButton>
      <SmallButton disabled={count < PAGE_SIZE} onClick={() => onChange(offset + PAGE_SIZE)}>
        Next →
      </SmallButton>
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-[10px] bg-paper-2" />
      ))}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="text-[13px] text-[#a4553f]">
      {children}
    </p>
  );
}

export function SectionHeader({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="font-display text-[20px] text-ink">{title}</h2>
        {hint && <p className="mt-0.5 text-[13px] text-muted">{hint}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}
