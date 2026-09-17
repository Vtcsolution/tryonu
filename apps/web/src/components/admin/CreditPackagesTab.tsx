"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { admin as adminApi } from "@/lib/api/endpoints";
import type { AdminCreditPackage } from "@/lib/api/types";
import { Badge, ErrorNote, SectionHeader, SmallButton, Table, TableSkeleton, errorText, inputClass, money } from "./ui";

export function CreditPackagesTab() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["admin", "credit-packages"], queryFn: adminApi.creditPackages });
  const [editing, setEditing] = useState<AdminCreditPackage | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "credit-packages"] });
    qc.invalidateQueries({ queryKey: ["admin", "audit"] });
  };

  const toggle = useMutation({
    mutationFn: (p: AdminCreditPackage) => adminApi.updateCreditPackage(p.id, { is_active: !p.is_active }),
    onSuccess: invalidate,
  });

  return (
    <div>
      <SectionHeader title="Credit packages" hint="What users can buy on the credits page. Inactive packages are hidden from the shop." />

      <PackageForm
        key={editing?.id ?? "new"}
        initial={editing}
        onDone={() => {
          setEditing(null);
          invalidate();
        }}
        onCancel={() => setEditing(null)}
      />

      {toggle.isError && <div className="mb-3"><ErrorNote>{errorText(toggle.error)}</ErrorNote></div>}

      {query.isLoading ? (
        <TableSkeleton />
      ) : query.isError || !query.data ? (
        <ErrorNote>{errorText(query.error, "Couldn't load credit packages.")}</ErrorNote>
      ) : (
        <Table
          columns={["Name", "Credits", "Price", "Per credit", "Status", ""]}
          rows={query.data.map((p) => [
            p.name,
            p.credits,
            money(p.price_cents, p.currency),
            `${(p.price_cents / 100 / p.credits).toFixed(3)} ${p.currency.toUpperCase()}`,
            p.is_active ? <Badge key="s" tone="good">On sale</Badge> : <Badge key="s">Hidden</Badge>,
            <div key="a" className="flex gap-1.5">
              <SmallButton onClick={() => setEditing(p)}>Edit</SmallButton>
              <SmallButton tone={p.is_active ? "danger" : "primary"} disabled={toggle.isPending} onClick={() => toggle.mutate(p)}>
                {p.is_active ? "Hide" : "Put on sale"}
              </SmallButton>
            </div>,
          ])}
          empty="No credit packages yet — create one above."
        />
      )}
    </div>
  );
}

function PackageForm({
  initial,
  onDone,
  onCancel,
}: {
  initial: AdminCreditPackage | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [credits, setCredits] = useState(initial?.credits.toString() ?? "");
  const [price, setPrice] = useState(initial ? (initial.price_cents / 100).toFixed(2) : "");

  const creditsNum = Number(credits);
  const priceCents = Math.round(Number(price) * 100);
  const valid = name.trim() && Number.isInteger(creditsNum) && creditsNum > 0 && priceCents > 0;

  const save = useMutation({
    mutationFn: () =>
      initial
        ? adminApi.updateCreditPackage(initial.id, { name: name.trim(), credits: creditsNum, price_cents: priceCents })
        : adminApi.createCreditPackage({ name: name.trim(), credits: creditsNum, price_cents: priceCents }),
    onSuccess: () => {
      if (!initial) {
        setName("");
        setCredits("");
        setPrice("");
      }
      onDone();
    },
  });

  return (
    <form
      className="mb-5 rounded-[16px] border border-line bg-surface p-4"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <p className="text-[13px] font-semibold text-ink">{initial ? `Edit “${initial.name}”` : "New package"}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" maxLength={120} className={`${inputClass} w-44`} />
        <input
          type="number"
          min={1}
          step={1}
          value={credits}
          onChange={(e) => setCredits(e.target.value)}
          placeholder="Credits"
          className={`${inputClass} w-28`}
        />
        <input
          type="number"
          min={0.01}
          step={0.01}
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="Price (USD)"
          className={`${inputClass} w-32`}
        />
        <SmallButton type="submit" tone="primary" disabled={!valid || save.isPending}>
          {save.isPending ? "Saving…" : initial ? "Save changes" : "Create"}
        </SmallButton>
        {initial && <SmallButton onClick={onCancel}>Cancel</SmallButton>}
      </div>
      {save.isError && <div className="mt-2"><ErrorNote>{errorText(save.error)}</ErrorNote></div>}
    </form>
  );
}
