"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { stores as storesApi } from "@/lib/api/endpoints";
import { WHATSAPP_GREEN, WhatsAppIcon } from "@/components/whatsapp/WhatsApp";
import type { PublicStore } from "@/lib/api/types";
import { useCart } from "./useCart";

export function waLink(number: string, text: string) {
  return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

/** A store's own website on TryOnU: its logo and name on top, its products,
 *  a cart, and a WhatsApp button always in reach. TryOnU only in the footer. */
export function StoreShell({
  store,
  children,
}: {
  store: PublicStore;
  children: ReactNode;
}) {
  const { count } = useCart(store.slug);
  const base = `/${store.slug}`;
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 tu-container items-center gap-3">
          <Link
            href={base}
            className="flex min-w-0 items-center gap-3"
            aria-label={`${store.name} home`}
          >
            {store.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={store.logo_url}
                alt=""
                className="h-10 w-10 shrink-0 rounded-xl border border-line object-cover"
              />
            ) : (
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-sage font-display text-[20px] text-white">
                {store.name.slice(0, 1).toUpperCase()}
              </span>
            )}
            <span
              translate="no"
              className="notranslate truncate font-display text-[20px] text-ink"
            >
              {store.name}
            </span>
          </Link>
          <nav
            className="ml-auto flex items-center gap-1 sm:gap-2"
            aria-label="Store"
          >
            <Link
              href={`${base}/products`}
              className="hidden rounded-full px-3 py-2 text-[15px] font-medium text-ink hover:bg-paper-2 sm:inline"
            >
              All products
            </Link>
            {store.whatsapp && (
              <a
                href={waLink(
                  store.whatsapp,
                  `Hi ${store.name}, I'm on your TryOnU store.`,
                )}
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
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.8a2 2 0 0 0 2-1.6L21 8H6" />
                <circle cx="10" cy="20" r="1.4" />
                <circle cx="18" cy="20" r="1.4" />
              </svg>
              Cart
              {count > 0 && (
                <span className="grid h-6 min-w-6 place-items-center rounded-full bg-sage px-1.5 text-[13px] font-bold text-white">
                  {count}
                </span>
              )}
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>
      <TryBar store={store} />

      {store.whatsapp && <FloatingWhatsApp store={store} number={store.whatsapp} />}

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex tu-container flex-wrap items-center justify-between gap-3 py-6 text-[14px] text-muted">
          <span translate="no" className="notranslate">
            © {new Date().getFullYear()} {store.name}
          </span>
          <a href="https://tryonu.app" className="hover:text-ink">
            Shop powered by <b className="text-ink">TryOnU</b>: try any product
            on your own photo
          </a>
        </div>
      </footer>
    </div>
  );
}

/** The products picked to try on, with one button that opens them all on
 *  TryOnU, already chosen: the shopper adds a photo and generates. */
function TryBar({ store }: { store: PublicStore }) {
  const picked = useCart(store.slug, "try");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  if (picked.count === 0) return null;
  const go = async () => {
    setBusy(true);
    setFailed(false);
    try {
      const chosen = await Promise.all(
        picked.lines.map((l) => storesApi.selectProduct(store.slug, l.id)),
      );
      const ids = chosen.map((c) => c.product_id);
      picked.clear();
      window.location.href =
        ids.length === 1
          ? `/try?product=${ids[0]}`
          : `/try?products=${ids.join(",")}`;
    } catch {
      setFailed(true);
      setBusy(false);
    }
  };
  return (
    <>
      <div aria-hidden="true" className="h-24" />
      <div className="fixed inset-x-0 bottom-0 z-50 border-t border-line bg-surface/95 px-4 py-3 shadow-lift backdrop-blur">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-3">
          <p className="mr-auto text-[15px] text-ink">
            <b>{picked.count}</b> {picked.count === 1 ? "product" : "products"}{" "}
            picked to try on together.
            <span className="text-muted"> Pick more, or try them now.</span>
          </p>
          <button
            type="button"
            onClick={() => picked.clear()}
            className="text-[14px] text-muted hover:text-ink"
          >
            Clear
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={go}
            className="tu-press inline-flex min-h-[46px] items-center rounded-full bg-sage px-5 text-[15.5px] font-semibold text-white disabled:opacity-60"
          >
            {busy
              ? "Opening…"
              : `Try on ${picked.count === 1 ? "this product" : `${picked.count} products`} →`}
          </button>
          {failed && (
            <p className="w-full text-[14px] text-[#a4553f]">
              A product couldn't be opened. Please try again.
            </p>
          )}
        </div>
      </div>
    </>
  );
}

/** The store's WhatsApp, always in the corner: a soft pulse so shoppers notice it,
 * moved up only while the try-on bar is open. */
function FloatingWhatsApp({ store, number }: { store: PublicStore; number: string }) {
  const picked = useCart(store.slug, "try");
  return (
    <a
      href={waLink(number, `Hi ${store.name}, I'm on your TryOnU store.`)}
      target="_blank"
      rel="noopener"
      aria-label={`Chat with ${store.name} on WhatsApp`}
      style={{ backgroundColor: WHATSAPP_GREEN }}
      className={`tu-wa-float fixed right-4 z-40 grid h-14 w-14 place-items-center rounded-full text-white shadow-lift transition-[bottom] duration-300 sm:right-6 ${
        picked.count > 0 ? "bottom-28" : "bottom-4 sm:bottom-6"
      }`}
    >
      <span aria-hidden="true" style={{ backgroundColor: WHATSAPP_GREEN }} className="tu-wa-ring absolute inset-0 rounded-full" />
      <span className="relative">
        <WhatsAppIcon size={28} />
      </span>
    </a>
  );
}
