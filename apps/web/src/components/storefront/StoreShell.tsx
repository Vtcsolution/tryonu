"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { WHATSAPP_GREEN, WhatsAppIcon } from "@/components/whatsapp/WhatsApp";
import type { PublicStore } from "@/lib/api/types";
import { useCart } from "./useCart";

export function waLink(number: string, text: string) {
  return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

/** A store's own website on TryOnU: its logo and name on top, its products,
 *  a cart, and a WhatsApp button always in reach. TryOnU only in the footer. */
export function StoreShell({ store, children }: { store: PublicStore; children: ReactNode }) {
  const { count } = useCart(store.slug);
  const base = `/${store.slug}`;
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 tu-container items-center gap-3">
          <Link href={base} className="flex min-w-0 items-center gap-3" aria-label={`${store.name} home`}>
            {store.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={store.logo_url} alt="" className="h-10 w-10 shrink-0 rounded-xl border border-line object-cover" />
            ) : (
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-sage font-display text-[20px] text-white">
                {store.name.slice(0, 1).toUpperCase()}
              </span>
            )}
            <span translate="no" className="notranslate truncate font-display text-[20px] text-ink">{store.name}</span>
          </Link>
          <nav className="ml-auto flex items-center gap-1 sm:gap-2" aria-label="Store">
            <Link href={`${base}/products`} className="hidden rounded-full px-3 py-2 text-[15px] font-medium text-ink hover:bg-paper-2 sm:inline">
              All products
            </Link>
            {store.whatsapp && (
              <a
                href={waLink(store.whatsapp, `Hi ${store.name}, I'm on your TryOnU store.`)}
                target="_blank"
                rel="noopener"
                aria-label={`WhatsApp ${store.name}`}
                style={{ backgroundColor: WHATSAPP_GREEN }}
                className="grid h-10 w-10 place-items-center rounded-full text-white"
              >
                <WhatsAppIcon size={20} />
              </a>
            )}
            <Link
              href={`${base}/cart`}
              className="relative inline-flex min-h-[40px] items-center gap-2 rounded-full border border-line-strong px-3.5 text-[15px] font-semibold text-ink hover:border-sage"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.8a2 2 0 0 0 2-1.6L21 8H6" />
                <circle cx="10" cy="20" r="1.4" />
                <circle cx="18" cy="20" r="1.4" />
              </svg>
              Cart
              {count > 0 && (
                <span className="grid h-6 min-w-6 place-items-center rounded-full bg-sage px-1.5 text-[13px] font-bold text-white">{count}</span>
              )}
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      {store.whatsapp && (
        <a
          href={waLink(store.whatsapp, `Hi ${store.name}, I'm on your TryOnU store.`)}
          target="_blank"
          rel="noopener"
          aria-label={`Chat with ${store.name} on WhatsApp`}
          style={{ backgroundColor: WHATSAPP_GREEN }}
          className="fixed bottom-5 right-5 z-40 grid h-14 w-14 place-items-center rounded-full text-white shadow-lift"
        >
          <WhatsAppIcon size={28} />
        </a>
      )}

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex tu-container flex-wrap items-center justify-between gap-3 py-6 text-[14px] text-muted">
          <span translate="no" className="notranslate">© {new Date().getFullYear()} {store.name}</span>
          <a href="https://tryonu.app" className="hover:text-ink">
            Shop powered by <b className="text-ink">TryOnU</b>: try any product on your own photo
          </a>
        </div>
      </footer>
    </div>
  );
}
