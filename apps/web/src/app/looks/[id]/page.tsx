import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { LookCanvas } from "@/components/looks/LookCanvas";
import { LookCollectionPage } from "@/components/looks/LookCollectionPage";
import { TryLookButton } from "@/components/looks/TryLookButton";
import { JsonLd, breadcrumbJsonLd } from "@/components/seo/JsonLd";
import { formatPrice } from "@/components/try/shop";
import type { ReadyLook } from "@/lib/api/endpoints";
import {
  LOOK_COLLECTIONS,
  lookCopy,
  lookDescription,
  lookPath,
  lookTitle,
  lookTotal,
  publishedLooks,
  resolveLookParam,
} from "@/lib/looks";
import { SITE, pageMeta } from "@/lib/seo";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const found = await resolveLookParam((await params).id);
  if (!found) return { title: "Look not found", robots: { index: false, follow: false } };
  if (found.kind === "redirect") return {};
  if (found.kind === "collection") {
    const c = found.collection;
    return pageMeta({ title: c.title, description: c.description, path: `/looks/${c.slug}`, image: found.looks[0]?.card_url });
  }
  const { look, published } = found;
  const title = lookTitle(look);
  const description = lookDescription(look);
  const path = published ? lookPath(look) : `/looks/${look.id}`;
  return {
    title: { absolute: title },
    description,
    alternates: { canonical: path },
    robots: published ? undefined : { index: false, follow: false },
    openGraph: { title, description, url: `${SITE}${path}`, images: [{ url: look.card_url, width: 1080, height: 1350, alt: look.title }], type: "article" },
    twitter: { card: "summary_large_image", title, description, images: [look.card_url] },
  };
}

/** /looks/<readable-address>: one Ready look, where the ads land. The outfit,
 * the blinking "Try this look on you first", every piece with its shop link,
 * and what to know about the look. Old id addresses redirect here; the
 * collections (/looks/women …) share the route. */
export default async function LookRoute({ params }: Props) {
  const found = await resolveLookParam((await params).id);
  if (!found) notFound();
  if (found.kind === "redirect") permanentRedirect(found.to);
  if (found.kind === "collection") return <LookCollectionPage collection={found.collection} looks={found.looks} />;
  const { look } = found;
  const more = (await publishedLooks()).filter((l) => l.id !== look.id && l.audience === look.audience).slice(0, 4);
  return <LookPage look={look} more={more} />;
}

function LookPage({ look, more }: { look: ReadyLook; more: ReadyLook[] }) {
  const tryPath = `/looks/${look.id}/try`;
  const path = lookPath(look);
  const total = lookTotal(look);
  const copy = lookCopy(look);
  const collection = LOOK_COLLECTIONS.find((c) => c.audience === look.audience);
  const list = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: look.title,
    url: `${SITE}${path}`,
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
  const crumbs = breadcrumbJsonLd([
    { name: "TryOnU", path: "/" },
    { name: "Ready looks", path: "/looks" },
    ...(collection ? [{ name: collection.h1.split(" ")[0], path: `/looks/${collection.slug}` }] : []),
    { name: look.title, path },
  ]);

  return (
    <SiteChrome>
      <JsonLd data={[list, crumbs]} />
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
              {total ? `, ${total} in total` : ""}. See them on your own photo before you buy.
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

        <div className="mt-12 grid max-w-5xl gap-8 md:grid-cols-2">
          <div>
            <h2 className="font-display text-[26px] text-ink">How to wear this look</h2>
            {copy.styling.map((p) => (
              <p key={p} className="mt-3 text-[16.5px] leading-relaxed text-ink-soft">{p}</p>
            ))}
          </div>
          <div>
            <h2 className="font-display text-[26px] text-ink">Where the pieces come from</h2>
            {copy.buying.map((p) => (
              <p key={p} className="mt-3 text-[16.5px] leading-relaxed text-ink-soft">{p}</p>
            ))}
            <p className="mt-3 text-[15px] text-muted">
              Your photo is used only for your own try-ons. Read the{" "}
              <Link href="/photo-policy" className="text-sage-deep underline">photo policy</Link> and{" "}
              <Link href="/privacy" className="text-sage-deep underline">privacy policy</Link>.
            </p>
          </div>
        </div>

        {more.length > 0 && (
          <div className="mt-14">
            <h2 className="font-display text-[26px] text-ink">More {look.audience === "kids" ? "kids'" : `${look.audience}'s`} looks</h2>
            <ul className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
              {more.map((l) => (
                <li key={l.id}>
                  <Link href={lookPath(l)} className="group block overflow-hidden rounded-[20px] border border-line bg-surface">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={l.card_small_url} alt={l.title} loading="lazy" className="aspect-[4/5] w-full object-cover" />
                    <span className="block p-3 text-[15px] font-semibold leading-snug text-ink group-hover:text-sage-deep">{l.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
            {collection && (
              <Link href={`/looks/${collection.slug}`} className="mt-5 inline-block text-[15.5px] font-semibold text-sage-deep hover:underline">
                See all {collection.h1.split(" ")[0].toLowerCase()} outfits →
              </Link>
            )}
          </div>
        )}
      </section>
    </SiteChrome>
  );
}
