"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { outfits as outfitsApi, products as productsApi } from "@/lib/api/endpoints";
import type { OutfitItemInput, OutfitSlot, Product } from "@/lib/api/types";

const SLOTS: OutfitSlot[] = ["top", "bottom", "dress", "outerwear", "shoes", "watch", "bag", "accessory", "other"];

type TrayEntry = { product: Product; slot: OutfitSlot };

export function OutfitBuilder({ onSaved }: { onSaved: () => void }) {
  const [tray, setTray] = useState<TrayEntry[]>([]);
  const [name, setName] = useState("");

  const productsQuery = useQuery({
    queryKey: ["products", "outfit-picker"],
    queryFn: () => productsApi.list({ limit: 24, sort: "newest" }),
  });

  const items: OutfitItemInput[] = useMemo(
    () => tray.map((t) => ({ product_id: t.product.id, slot: t.slot })),
    [tray],
  );

  const previewQuery = useQuery({
    queryKey: ["outfit-preview", items],
    queryFn: () => outfitsApi.previewCompatibility(items),
    enabled: items.length >= 2,
  });

  const save = useMutation({
    mutationFn: () => outfitsApi.create({ name: name || undefined, items }),
    onSuccess: onSaved,
  });

  const totalCents = tray.reduce((sum, t) => sum + t.product.price_cents, 0);

  const toggleProduct = (product: Product) => {
    setTray((cur) => {
      if (cur.some((t) => t.product.id === product.id)) return cur.filter((t) => t.product.id !== product.id);
      if (cur.length >= 8) return cur;
      return [...cur, { product, slot: "other" }];
    });
  };

  const setSlot = (productId: string, slot: OutfitSlot) => {
    setTray((cur) => cur.map((t) => (t.product.id === productId ? { ...t, slot } : t)));
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div>
        <p className="mb-3 text-[13px] font-semibold text-ink-soft">Pick products to combine</p>
        {productsQuery.isLoading && (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] animate-pulse rounded-[14px] bg-paper-2" />
            ))}
          </div>
        )}
        {productsQuery.data && (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
            {productsQuery.data.items.map((p) => {
              const selected = tray.some((t) => t.product.id === p.id);
              const thumb = resolveMediaUrl(p.images[0]?.url);
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => toggleProduct(p)}
                  className={`overflow-hidden rounded-[14px] border text-left transition-colors ${
                    selected ? "border-sage ring-2 ring-sage/30" : "border-line hover:border-line-strong"
                  }`}
                >
                  <div className="relative aspect-[3/4] bg-paper-2">
                    {thumb && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={thumb} alt={p.name} className="h-full w-full object-cover object-top" />
                    )}
                    {selected && (
                      <span className="absolute right-1.5 top-1.5 grid h-5 w-5 place-items-center rounded-full bg-sage text-[10px] text-white">
                        ✓
                      </span>
                    )}
                  </div>
                  <div className="p-2">
                    <p className="truncate text-[11px] font-semibold text-ink">{p.name}</p>
                    <p className="text-[10.5px] text-muted">{(p.price_cents / 100).toFixed(2)}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4 rounded-[20px] border border-line bg-surface p-4">
        <div>
          <span className="mb-1.5 block text-[13px] font-medium text-ink-soft">Outfit name (optional)</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Weekend brunch"
            className="h-10 w-full rounded-xl border border-line-strong bg-paper px-3 text-[13px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
          />
        </div>

        {tray.length === 0 && (
          <p className="text-[13px] text-muted">Select at least 2 products to see a compatibility score.</p>
        )}

        <div className="flex flex-col gap-2.5">
          {tray.map((t) => (
            <div key={t.product.id} className="flex items-center gap-2.5">
              <div className="h-12 w-10 shrink-0 overflow-hidden rounded-[8px] bg-paper-2">
                {resolveMediaUrl(t.product.images[0]?.url) && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={resolveMediaUrl(t.product.images[0]?.url)}
                    alt={t.product.name}
                    className="h-full w-full object-cover object-top"
                  />
                )}
              </div>
              <p className="flex-1 truncate text-[12px] text-ink">{t.product.name}</p>
              <select
                value={t.slot}
                onChange={(e) => setSlot(t.product.id, e.target.value as OutfitSlot)}
                className="h-8 rounded-lg border border-line-strong bg-paper px-1.5 text-[11px] text-ink-soft"
              >
                {SLOTS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => toggleProduct(t.product)}
                aria-label="Remove"
                className="text-faint hover:text-[#a4553f]"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        {tray.length >= 2 && (
          <div className="rounded-[14px] border border-line bg-paper-2 p-3">
            {previewQuery.isLoading && <p className="text-[12px] text-muted">Scoring…</p>}
            {previewQuery.data && (
              <>
                <p className="text-[13px] font-semibold text-ink">{previewQuery.data.overall}% compatibility</p>
                {previewQuery.data.notes.length > 0 && (
                  <ul className="mt-1.5 space-y-1 text-[11.5px] text-muted">
                    {previewQuery.data.notes.map((n) => (
                      <li key={n}>· {n}</li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}

        {tray.length > 0 && (
          <p className="text-[13px] text-ink-soft">Total: {(totalCents / 100).toFixed(2)}</p>
        )}

        {save.isError && (
          <p role="alert" className="text-[12.5px] text-[#a4553f]">
            {save.error instanceof ApiError ? save.error.detail : "Couldn't save this outfit."}
          </p>
        )}

        <Button size="md" disabled={tray.length === 0 || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save outfit"}
        </Button>
      </div>
    </div>
  );
}
