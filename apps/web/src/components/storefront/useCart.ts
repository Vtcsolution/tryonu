"use client";

import { useCallback, useEffect, useState } from "react";

/** One store's cart on this device: product ids and how many. */
export type CartLine = { id: string; qty: number };

const EVENT = "tu-cart-change";
type Kind = "cart" | "try";
const key = (slug: string, kind: Kind) => `tu-${kind}-${slug}`;

function read(slug: string, kind: Kind = "cart"): CartLine[] {
  try {
    const lines = JSON.parse(localStorage.getItem(key(slug, kind)) || "[]");
    return Array.isArray(lines) ? lines.filter((l) => l && typeof l.id === "string" && l.qty > 0) : [];
  } catch {
    return [];
  }
}

/** kind "try": the products picked to try on together (qty is always 1) */
export function useCart(slug: string, kind: Kind = "cart") {
  const [lines, setLines] = useState<CartLine[]>([]);
  useEffect(() => {
    const sync = () => setLines(read(slug, kind));
    sync();
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [slug, kind]);

  const save = useCallback(
    (next: CartLine[]) => {
      try {
        localStorage.setItem(key(slug, kind), JSON.stringify(next.filter((l) => l.qty > 0)));
      } catch {
        /* private mode: the cart lasts this visit */
      }
      setLines(next.filter((l) => l.qty > 0));
      window.dispatchEvent(new Event(EVENT));
    },
    [slug, kind],
  );

  const add = (id: string, qty = 1) => {
    const now = read(slug, kind);
    const found = now.find((l) => l.id === id);
    save(found ? now.map((l) => (l.id === id ? { ...l, qty: Math.min(20, l.qty + qty) } : l)) : [...now, { id, qty }]);
  };
  const setQty = (id: string, qty: number) => save(read(slug, kind).map((l) => (l.id === id ? { ...l, qty: Math.max(0, Math.min(20, qty)) } : l)));
  const remove = (id: string) => save(read(slug, kind).filter((l) => l.id !== id));
  const has = (id: string) => lines.some((l) => l.id === id);
  const toggle = (id: string) => (read(slug, kind).some((l) => l.id === id) ? remove(id) : add(id));
  const clear = () => save([]);
  const count = lines.reduce((n, l) => n + l.qty, 0);
  return { lines, add, setQty, remove, clear, count, has, toggle };
}
