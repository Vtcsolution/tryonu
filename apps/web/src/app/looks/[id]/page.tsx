import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { LookCanvas } from "@/components/looks/LookCanvas";
import { TryLookButton } from "@/components/looks/TryLookButton";
import { JsonLd } from "@/components/seo/JsonLd";
import { formatPrice } from "@/components/try/shop";
import type { ReadyLook } from "@/lib/api/endpoints";
import { serverFetch } from "@/lib/api/server";
import { SITE } from "@/lib/seo";

type Props = { params: Promise<{ id: string }> };

async function load(id: string): Promise<ReadyLook | null> {
  return serverFetch<ReadyLook>(`/api/v1/looks/${encodeURIComponent(id)}`, { revalidateSeconds: 120 });
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const look = await load((await params).id);
  if (!look) return { title: "Look not found", robots: { index: false, follow: false } };
  const pieces = look.items.map((p) => p.name).slice(0, 4).join(", ");
  const title = `${look.title}: Try It On You | TryOnU`;
  const description = `${pieces}. See this complete look on your own photo with TryOnU, then buy each piece from its shop.`.slice(0, 158);
  return {
    title: { absolute: title },
    description,
    alternates: { canonical: `/looks/${look.id}` },
    openGraph: { title, description, url: `${SITE}/looks/${look.id}`, images: [{ url: look.card_url, width: 1080, height: 1350, alt: look.title }], type: "article" },
    twitter: { card: "summary_large_image", title, description, images: [look.card_url] },
  };
}

/** One Ready look: where the ads land. The outfit at the top, the blinking
 * "Try this look on you first", and every piece with its shop link. */
export default async function LookPage({ params }: Props) {
  const look = await load((await params).id);
  if (!look) notFound();
  const tryPath = `/looks/${look.id}/try`;
  const list = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: look.title,
    url: `${SITE}/looks/${look.id}`,
    image: look.card_url,
    itemListElement: look.items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      item: {
        "@type": "Product",
        name: it.name,
        image: it.image_url ?? undefined,
        offers: { "@type": "Offer", price: (it.price_cents / 100).toFixed(2), priceCurrency: it.currency.toUpperCase(), url: it.buy_url },
      },
    })),
  };

  return (
    <SiteChrome>
      <JsonLd data={list} />
      <section className="tu-container py-6 md:py-10">
        <Link href="/looks" className="text-[14.5px] font-semibold text-sage-deep hover:underline">
          ← All ready looks
        </Link>
        <div className="mt-4 grid items-start gap-8 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)] lg:gap-12">
          <div className="overflow-hidden rounded-[26px] border border-line bg-paper-2 shadow-lift">
            <LookCanvas look={look} priority />
          </div>

          <div className="min-w-0">
            {look.season && (
              <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">{look.season} look</p>
            )}
            <h1 className="mt-1 font-display text-[clamp(30px,4.2vw,46px)] leading-tight text-ink">{look.title}</h1>
            <p className="mt-2 text-[16px] text-ink-soft">
              {look.items.length} {look.items.length === 1 ? "piece" : "pieces"} from real shops
              {look.total_cents != null && look.currency ? `, ${formatPrice(look.total_cents, look.currency)} in total` : ""}. See
              them on your own photo before you buy.
            </p>

            <TryLookButton lookId={look.id} className="mt-6 w-full sm:w-auto" />
            <FirstOutfitOffer variant="banner" next={tryPath} className="mt-5" />

            <h2 className="mt-8 text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Every piece in this look</h2>
            <ul className="mt-3 space-y-3">
              {look.items.map((it) => (
                <li key={it.id}>
                  <a
                    href={it.buy_url}
                    target="_blank"
                    rel="noopener sponsored"
                    className="group flex items-center gap-4 rounded-[20px] border border-line bg-surface p-3 pr-4 transition-colors hover:border-sage"
                  >
                    <span className="h-20 w-20 shrink-0 overflow-hidden rounded-2xl bg-white">
                      {it.image_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={it.image_url} alt={it.name} loading="lazy" className="h-full w-full object-contain p-1.5" />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 text-[16px] font-semibold leading-snug text-ink">{it.name}</span>
                      <span className="mt-0.5 block text-[14px] text-muted">{it.shop}</span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block text-[17px] font-bold text-ink">{formatPrice(it.price_cents, it.currency)}</span>
                      <span className="block text-[14px] font-semibold text-sage-deep group-hover:underline">Shop →</span>
                    </span>
                  </a>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-[13.5px] text-muted">
              Shown on an AI-generated model with a real TryOnU try-on. You buy from each shop, at its own price.
            </p>
          </div>
        </div>
      </section>
    </SiteChrome>
  );
}
