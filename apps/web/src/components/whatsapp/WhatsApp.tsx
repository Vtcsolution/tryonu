"use client";

import { useQuery } from "@tanstack/react-query";
import { contact, orderOptions, whatsappOrderUrl } from "@/lib/api/endpoints";

export const WHATSAPP_GREEN = "#1fa855";

export function WhatsAppIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.2-.2-.5-.3Z" />
    </svg>
  );
}

/** "Order on WhatsApp", for products of local TryOnU stores that take WhatsApp orders. Nothing otherwise. */
export function WhatsAppOrderButton({ productId, source }: { productId: string; source: string }) {
  const options = useQuery({
    queryKey: ["order-options", productId],
    queryFn: () => orderOptions(productId),
    staleTime: 10 * 60_000,
    retry: false,
  });
  if (!options.data?.whatsapp) return null;
  return (
    <a
      href={whatsappOrderUrl(productId, source)}
      target="_blank"
      rel="noopener"
      style={{ backgroundColor: WHATSAPP_GREEN }}
      className="tu-press flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full px-4 text-[15.5px] font-semibold text-white"
    >
      <WhatsAppIcon /> Order on WhatsApp
    </a>
  );
}

export function useHelpWhatsApp(): string | null {
  const info = useQuery({ queryKey: ["contact-info"], queryFn: contact.info, staleTime: 30 * 60_000, retry: false });
  return info.data?.whatsapp ?? null;
}

const HELLO = "Hi TryOnU, I need help with: ";

/** "Chat with us on WhatsApp": hidden until an admin sets the number (Admin → Settings → Help & contact). */
export function HelpWhatsApp({ variant = "card" }: { variant?: "card" | "row" }) {
  const number = useHelpWhatsApp();
  if (!number) return null;
  const href = `https://wa.me/${number}?text=${encodeURIComponent(HELLO)}`;
  if (variant === "row") {
    return (
      <a href={href} target="_blank" rel="noopener" className="tu-tap flex min-h-[54px] items-center gap-3 rounded-2xl border border-line bg-surface px-4 active:bg-paper-2">
        <span style={{ color: WHATSAPP_GREEN }}>
          <WhatsAppIcon size={22} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[16px] text-ink">Chat with us on WhatsApp</span>
          <span className="block text-[13px] text-muted">Questions? We're happy to help</span>
        </span>
      </a>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener"
      className="flex items-center gap-3 rounded-[18px] border border-line bg-surface p-4 transition-colors hover:border-line-strong"
    >
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-white" style={{ backgroundColor: WHATSAPP_GREEN }}>
        <WhatsAppIcon size={24} />
      </span>
      <span className="min-w-0">
        <span className="block text-[16px] font-semibold text-ink">Chat with us on WhatsApp</span>
        <span className="block text-[14px] text-muted">The quickest way to get help</span>
      </span>
    </a>
  );
}
