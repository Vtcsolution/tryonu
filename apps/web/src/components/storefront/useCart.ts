"use client";

import { useCallback, useEffect, useState } from "react";

/** One store's cart on this device: product ids and how many. */
export type CartLine = { id: string; qty: number };

const key = (slug: string) => `tu-cart-${slug}`;
const EVENT = "tu-cart-change";

function read(slug: string): CartLine[] {
  try {
    const lines = JSON.parse(localStorage.getItem(key(slug)) || "[]");
    return Array.isArray(lines) ? lines.filter((l) => l && typeof l.id === "string" && l.qty > 0) : [];
  } catch {
    return [];
  }
}

export function useCart(slug: string) {
  const [lines, setLines] = useState<CartLine[]>([]);
  useEffect(() => {
    const sync = () => setLines(read(slug));
    sync();
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [slug]);

  const save = useCallback(
    (next: CartLine[]) => {
      try {
        localStorage.setItem(key(slug), JSON.stringify(next.filter((l) => l.qty > 0)));
      } catch {
        /* private mode: the cart lasts this visit */
      }
      setLines(next.filter((l) => l.qty > 0));
      window.dispatchEvent(new Event(EVENT));
    },
    [slug],
  );

  const add = (id: string, qty = 1) => {
    const now = read(slug);
    const found = now.find((l) => l.id === id);
    save(found ? now.map((l) => (l.id === id ? { ...l, qty: Math.min(20, l.qty + qty) } : l)) : [...now, { id, qty }]);
  };
  const setQty = (id: string, qty: number) => save(read(slug).map((l) => (l.id === id ? { ...l, qty: Math.max(0, Math.min(20, qty)) } : l)));
  const remove = (id: string) => save(read(slug).filter((l) => l.id !== id));
  const clear = () => save([]);
  const count = lines.reduce((n, l) => n + l.qty, 0);
  return { lines, add, setQty, remove, clear, count };
}
