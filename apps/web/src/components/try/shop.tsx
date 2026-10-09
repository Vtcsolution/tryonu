/** Shared bits for showing where a product comes from and what it costs. */

/** The shop to name: an affiliate network's product (Admitad) names the
 *  programme that sells it, shortened ("Allegra K Many GEOs" -> "Allegra K"). */
export function shopName(merchant?: string | null, retailer?: string | null): string | null {
  const shop = merchant?.replace(/\s+(Many GEOs|Many Geos|WW|[A-Z]{2}(,\s*[A-Z]{2})*)$/, "").trim();
  return shop || retailer || null;
}

/** Which shop a product comes from, as a small tag on its card. */
export function RetailerTag({ name, className = "" }: { name?: string | null; className?: string }) {
  if (!name) return null;
  return (
    <span
      className={`rounded-full bg-surface/95 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-ink-soft shadow-sm ${className}`}
    >
      {name}
    </span>
  );
}

/** The shop behind a product photo, from where the photo is hosted: used for
 *  earlier-round items, whose saved placement keeps the photo but not the shop. */
export function retailerFromImage(url?: string | null): string | null {
  if (!url) return null;
  if (/ebayimg\.com/.test(url)) return "eBay";
  if (/alicdn\.com|aliexpress/.test(url)) return "AliExpress";
  return null;
}

/** "$54.99", "€389.00": the currency's own symbol where the browser knows it. */
export function formatPrice(cents: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase() }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`;
  }
}
