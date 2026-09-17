"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { resolveMediaUrl } from "@/lib/api/client";
import { admin as adminApi } from "@/lib/api/endpoints";
import type { AdminRetailer } from "@/lib/api/types";
import {
  Badge,
  ErrorNote,
  PAGE_SIZE,
  Pager,
  SectionHeader,
  SmallButton,
  Table,
  TableSkeleton,
  errorText,
  inputClass,
  money,
  when,
} from "./ui";

export function ProductsTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [visibility, setVisibility] = useState<"all" | "visible" | "hidden">("all");
  const [offset, setOffset] = useState(0);

  const active = visibility === "all" ? undefined : visibility === "visible";
  const query = useQuery({
    queryKey: ["admin", "products", q, visibility, offset],
    queryFn: () => adminApi.products({ q: q || undefined, active, limit: PAGE_SIZE, offset }),
  });

  const toggle = useMutation({
    mutationFn: (input: { id: string; is_active: boolean }) => adminApi.updateProduct(input.id, { is_active: input.is_active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "products"] });
      qc.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
  });

  return (
    <div>
      <SectionHeader
        title="Products"
        hint="Products users have actually selected or tried on. Hiding one also removes it from live search results site-wide."
      >
        <form
          className="flex gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setOffset(0);
            setQ(search.trim());
          }}
        >
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name or brand"
            className={`${inputClass} w-48`}
          />
          <SmallButton type="submit" tone="primary">
            Search
          </SmallButton>
        </form>
        <select
          value={visibility}
          onChange={(e) => {
            setVisibility(e.target.value as typeof visibility);
            setOffset(0);
          }}
          className={inputClass}
        >
          <option value="all">All</option>
          <option value="visible">Visible</option>
          <option value="hidden">Hidden</option>
        </select>
      </SectionHeader>

      {toggle.isError && <div className="mb-3"><ErrorNote>{errorText(toggle.error)}</ErrorNote></div>}

      {query.isLoading ? (
        <TableSkeleton />
      ) : query.isError || !query.data ? (
        <ErrorNote>{errorText(query.error, "Couldn't load products.")}</ErrorNote>
      ) : (
        <>
          <Table
            columns={["", "Product", "Retailer", "Price", "Saved", "Visibility", ""]}
            rows={query.data.items.map((p) => [
              p.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img key="i" src={resolveMediaUrl(p.image_url)} alt="" className="h-12 w-10 rounded-md object-cover object-top" />
              ) : (
                ""
              ),
              <a
                key="n"
                href={p.product_url}
                target="_blank"
                rel="noopener noreferrer"
                className="line-clamp-2 max-w-[280px] hover:underline"
              >
                {p.name}
              </a>,
              p.retailer_name,
              money(p.price_cents, p.currency),
              when(p.created_at),
              p.is_active ? <Badge key="v" tone="good">Visible</Badge> : <Badge key="v" tone="bad">Hidden</Badge>,
              p.is_active ? (
                <SmallButton
                  key="t"
                  tone="danger"
                  disabled={toggle.isPending}
                  onClick={() => {
                    if (window.confirm(`Hide “${p.name}” everywhere on TryOnU, including live search?`)) {
                      toggle.mutate({ id: p.id, is_active: false });
                    }
                  }}
                >
                  Hide
                </SmallButton>
              ) : (
                <SmallButton key="t" disabled={toggle.isPending} onClick={() => toggle.mutate({ id: p.id, is_active: true })}>
                  Unhide
                </SmallButton>
              ),
            ])}
            empty="No products match."
          />
          <Pager offset={offset} total={query.data.total} onChange={setOffset} />
        </>
      )}
    </div>
  );
}

export function RetailersTab() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["admin", "retailers"], queryFn: adminApi.retailers });

  const update = useMutation({
    mutationFn: (input: { slug: string; is_active?: boolean; base_commission_pct?: number | null }) =>
      adminApi.updateRetailer(input.slug, { is_active: input.is_active, base_commission_pct: input.base_commission_pct }),
    onSuccess: (rows) => {
      qc.setQueryData(["admin", "retailers"], rows);
      qc.invalidateQueries({ queryKey: ["admin", "audit"] });
      qc.invalidateQueries({ queryKey: ["admin", "overview"] });
    },
  });

  return (
    <div>
      <SectionHeader
        title="Retailers & integrations"
        hint="Disabling a retailer stops it being searched immediately. Commission only earns once tracking is configured."
      />
      {update.isError && <div className="mb-3"><ErrorNote>{errorText(update.error)}</ErrorNote></div>}

      {query.isLoading ? (
        <TableSkeleton />
      ) : query.isError || !query.data ? (
        <ErrorNote>{errorText(query.error, "Couldn't load retailers.")}</ErrorNote>
      ) : (
        <Table
          columns={["Retailer", "Integration", "Credentials", "Commission tracking", "Saved products", "Commission %", "Enabled"]}
          rows={query.data.map((r) => [
            <div key="n">
              <p className="font-medium">{r.name}</p>
              <p className="text-[11px] text-faint">{r.slug}</p>
            </div>,
            r.integration_built ? <Badge key="i" tone="good">Built</Badge> : <Badge key="i">Not built yet</Badge>,
            r.credentials_configured ? <Badge key="c" tone="good">Set</Badge> : <Badge key="c" tone="bad">Missing</Badge>,
            r.commission_tracking_configured === null ? (
              <span key="t" className="text-faint">—</span>
            ) : r.commission_tracking_configured ? (
              <Badge key="t" tone="good">Set</Badge>
            ) : (
              <Badge key="t" tone="warn">Not earning</Badge>
            ),
            r.saved_products,
            <CommissionInput key="p" retailer={r} disabled={update.isPending} onSave={(pct) => update.mutate({ slug: r.slug, base_commission_pct: pct })} />,
            <SmallButton
              key="e"
              tone={r.is_active ? "danger" : "primary"}
              disabled={update.isPending}
              onClick={() => {
                if (!r.is_active || window.confirm(`Disable ${r.name}? Its products stop appearing in search immediately.`)) {
                  update.mutate({ slug: r.slug, is_active: !r.is_active });
                }
              }}
            >
              {r.is_active ? "Disable" : "Enable"}
            </SmallButton>,
          ])}
        />
      )}
    </div>
  );
}

function CommissionInput({
  retailer,
  disabled,
  onSave,
}: {
  retailer: AdminRetailer;
  disabled: boolean;
  onSave: (pct: number | null) => void;
}) {
  const [value, setValue] = useState(retailer.base_commission_pct?.toString() ?? "");
  const current = retailer.base_commission_pct?.toString() ?? "";
  const parsed = value.trim() === "" ? null : Number(value);
  const valid = parsed === null || (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 100);

  return (
    <div className="flex items-center gap-1.5">
      <input
        type="number"
        min={0}
        max={100}
        step={0.1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="—"
        className={`${inputClass} w-20`}
      />
      {value !== current && (
        <SmallButton tone="primary" disabled={disabled || !valid} onClick={() => onSave(parsed)}>
          Save
        </SmallButton>
      )}
    </div>
  );
}
