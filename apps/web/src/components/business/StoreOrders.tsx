"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, ErrorNote, SmallButton, errorText } from "@/components/admin/ui";
import { formatPrice } from "@/components/try/shop";
import { WHATSAPP_GREEN, WhatsAppIcon } from "@/components/whatsapp/WhatsApp";
import { stores as storesApi, type StoreOrder } from "@/lib/api/endpoints";
import type { Store } from "@/lib/api/types";

const STEPS: [StoreOrder["status"], string][] = [
  ["new", "New"],
  ["confirmed", "Confirmed"],
  ["shipped", "Sent"],
  ["delivered", "Delivered"],
  ["cancelled", "Cancelled"],
];
const TONE: Record<StoreOrder["status"], "warn" | "good" | "neutral" | "bad"> = {
  new: "warn",
  confirmed: "neutral",
  shipped: "neutral",
  delivered: "good",
  cancelled: "bad",
};

/** Your store's own website address, to share anywhere (WhatsApp status, Instagram bio). */
export function StoreLink({ store }: { store: Store }) {
  const url = `https://tryonu.app/${store.slug}`;
  const [copied, setCopied] = useState(false);
  return (
    <div className="rounded-[20px] border border-sage/40 bg-sage-tint/40 p-5">
      <p className="text-[14px] font-semibold uppercase tracking-[0.12em] text-sage-deep">Your store website</p>
      <p translate="no" className="notranslate mt-1 break-all font-display text-[22px] text-ink">
        tryonu.app/{store.slug}
      </p>
      <p className="mt-1 text-[14.5px] text-muted">
        Only your products, with your name and logo. Customers add to cart and order; you get each order by email, and they
        can send it to your WhatsApp.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a href={url} target="_blank" rel="noopener" className="inline-flex min-h-[40px] items-center rounded-full bg-sage px-4 text-[14.5px] font-semibold text-white">
          Open my store ↗
        </a>
        <button
          type="button"
          onClick={() => {
            navigator.clipboard
              ?.writeText(url)
              .then(() => setCopied(true))
              .catch(() => undefined);
          }}
          className="min-h-[40px] rounded-full border border-line-strong bg-surface px-4 text-[14.5px] font-semibold text-ink"
        >
          {copied ? "Copied" : "Copy link"}
        </button>
        <a
          href={`https://wa.me/?text=${encodeURIComponent(`Shop ${store.name} online and try clothes on your own photo: ${url}`)}`}
          target="_blank"
          rel="noopener"
          style={{ backgroundColor: WHATSAPP_GREEN }}
          className="inline-flex min-h-[40px] items-center gap-2 rounded-full px-4 text-[14.5px] font-semibold text-white"
        >
          <WhatsAppIcon size={16} /> Share on WhatsApp
        </a>
      </div>
      {!store.whatsapp && (
        <p className="mt-3 text-[14px] text-ink">
          Add your WhatsApp number in <b>Edit store</b>: a WhatsApp button then shows on your store, and customers can send you
          their orders there.
        </p>
      )}
    </div>
  );
}

function waNumber(phone: string): string | null {
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 7) return null;
  return digits.startsWith("00") ? digits.slice(2) : digits;
}

/** Orders from your store website: call or WhatsApp the customer, then move the order along. */
export function OrdersSection() {
  const qc = useQueryClient();
  const [show, setShow] = useState<string>("all");
  const orders = useQuery({ queryKey: ["store-orders", show], queryFn: () => storesApi.myOrders(show), refetchInterval: 60_000 });
  const move = useMutation({
    mutationFn: ({ id, status }: { id: string; status: StoreOrder["status"] }) => storesApi.updateOrder(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["store-orders"] }),
  });
  const filters: [string, string][] = [["all", "All"], ...STEPS];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto font-display text-[24px] text-ink">Orders</h2>
        {filters.map(([value, label]) => (
          <SmallButton key={value} tone={show === value ? "primary" : undefined} onClick={() => setShow(value)}>
            {label}
            {value === "new" && orders.data?.new ? ` (${orders.data.new})` : ""}
          </SmallButton>
        ))}
      </div>
      <p className="text-[14.5px] text-muted">
        Orders from your store website. You also get each one by email. Contact the customer to confirm delivery and payment.
        When you change an order&apos;s step, customers who gave their email are told.
      </p>
      {orders.isError && <ErrorNote>{errorText(orders.error)}</ErrorNote>}
      {move.isError && <ErrorNote>{errorText(move.error)}</ErrorNote>}
      {orders.data && orders.data.items.length === 0 && (
        <p className="rounded-[16px] border border-dashed border-line p-8 text-center text-[15px] text-muted">
          No orders yet. Share your store link to get your first one.
        </p>
      )}
      {orders.data?.items.map((o) => {
        const wa = waNumber(o.phone);
        return (
          <article key={o.id} className="rounded-[18px] border border-line bg-surface p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[16px] font-semibold text-ink">{o.number}</p>
              <Badge tone={TONE[o.status]}>{STEPS.find(([v]) => v === o.status)?.[1]}</Badge>
              <span className="ml-auto text-[13.5px] text-faint">{new Date(o.created_at).toLocaleString()}</span>
            </div>
            <ul className="mt-2 space-y-0.5 text-[14.5px] text-ink">
              {o.items.map((it) => (
                <li key={it.product_id}>
                  {it.qty} × {it.name} · {formatPrice(it.price_cents * it.qty, o.currency)}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-[15px] font-bold text-ink">Total {formatPrice(o.total_cents, o.currency)}</p>
            <p className="mt-2 text-[14.5px] text-ink-soft">
              <b>{o.customer_name}</b> · {o.phone}
              {o.email ? ` · ${o.email}` : ""}
              <br />
              {o.address}
              {o.city ? `, ${o.city}` : ""}
              {o.note ? ` · Note: ${o.note}` : ""}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {wa && (
                <a
                  href={`https://wa.me/${wa}?text=${encodeURIComponent(`Hi ${o.customer_name}, thank you for your order ${o.number}.`)}`}
                  target="_blank"
                  rel="noopener"
                  style={{ backgroundColor: WHATSAPP_GREEN }}
                  className="inline-flex min-h-[36px] items-center gap-1.5 rounded-full px-3 text-[13.5px] font-semibold text-white"
                >
                  <WhatsAppIcon size={14} /> WhatsApp
                </a>
              )}
              <a href={`tel:${o.phone}`} className="inline-flex min-h-[36px] items-center rounded-full border border-line-strong px-3 text-[13.5px] font-semibold text-ink">
                Call
              </a>
              <label className="ml-auto flex items-center gap-2 text-[13.5px] text-ink-soft">
                Step
                <select
                  value={o.status}
                  disabled={move.isPending}
                  onChange={(e) => move.mutate({ id: o.id, status: e.target.value as StoreOrder["status"] })}
                  className="h-9 rounded-full border border-line-strong bg-paper px-3 text-[14px] text-ink"
                >
                  {STEPS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </article>
        );
      })}
    </div>
  );
}
