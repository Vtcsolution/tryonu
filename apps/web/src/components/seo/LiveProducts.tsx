import Link from "next/link";
import { formatPrice } from "@/components/try/shop";
import { serverFetch } from "@/lib/api/server";
import type { LiveProduct } from "@/lib/api/types";
import { shortName } from "@/lib/looks";

/** Real products from the live search (eBay, AliExpress, brand stores),
 * fetched on the server so the page shows them in its HTML. Each opens the
 * try-on studio with the same search ready. Nothing shows if the search fails. */
export async function LiveProducts({ query, limit }: { query: string; limit: number }) {
  const items =
    (await serverFetch<LiveProduct[]>(`/api/v1/search/live?q=${encodeURIComponent(query)}&limit=${limit}`, { revalidateSeconds: 21600 })) ?? [];
  const shown = items.filter((p) => p.images[0]).slice(0, limit);
  if (shown.length === 0) return null;
  const tryHref = `/try?q=${encodeURIComponent(query)}`;
  return (
    <div>
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {shown.map((p) => (
          <li key={`${p.retailer_slug}:${p.retailer_product_id}`}>
            <Link href={tryHref} className="group block h-full overflow-hidden rounded-[20px] border border-line bg-surface hover:border-sage">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={p.images[0]} alt={p.name} loading="lazy" className="aspect-square w-full bg-white object-contain p-2" />
              <span className="block px-3 pt-2 text-[14.5px] font-semibold leading-snug text-ink group-hover:text-sage-deep">{shortName(p.name)}</span>
              <span className="block px-3 pb-3 pt-0.5 text-[13.5px] text-muted">
                {formatPrice(p.price_cents, p.currency)} · {p.merchant_name || p.retailer_name}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[14px] text-muted">Live from real shops; prices and stock change. Tap one to try it on your photo.</p>
    </div>
  );
}
