import Link from "next/link";
import { FirstOutfitOffer } from "@/components/credits/FirstOutfitOffer";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { JsonLd, breadcrumbJsonLd } from "@/components/seo/JsonLd";
import type { ReadyLook } from "@/lib/api/endpoints";
import { LOOK_COLLECTIONS, type LookCollection, lookPath, lookTotal } from "@/lib/looks";
import { SITE } from "@/lib/seo";

/** A server-rendered grid of looks, each linking to its own page (readable by search engines). */
export function LookCards({ looks }: { looks: ReadyLook[] }) {
  return (
    <ul className="grid grid-cols-1 gap-6 min-[480px]:grid-cols-2 lg:grid-cols-3">
      {looks.map((l) => {
        const total = lookTotal(l);
        return (
          <li key={l.id}>
            <Link href={lookPath(l)} className="group block overflow-hidden rounded-[24px] border border-line bg-surface">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={l.card_small_url} alt={l.title} loading="lazy" className="aspect-[4/5] w-full object-cover" />
              <span className="block px-4 pt-4 text-[18px] font-semibold leading-snug text-ink group-hover:text-sage-deep">{l.title}</span>
              <span className="block px-4 pb-4 pt-0.5 text-[14.5px] text-muted">
                {l.items.length} {l.items.length === 1 ? "product" : "products"}
                {total ? ` · ${total} in total` : ""}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** /looks/women, /looks/men, /looks/winter: a collection of ready looks. */
export function LookCollectionPage({ collection, looks }: { collection: LookCollection; looks: ReadyLook[] }) {
  const path = `/looks/${collection.slug}`;
  const others = LOOK_COLLECTIONS.filter((c) => c.slug !== collection.slug);
  return (
    <SiteChrome>
      <JsonLd
        data={[
          {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            name: collection.h1,
            url: `${SITE}${path}`,
            description: collection.description,
            mainEntity: {
              "@type": "ItemList",
              itemListElement: looks.map((l, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE}${lookPath(l)}`, name: l.title, image: l.card_url })),
            },
          },
          breadcrumbJsonLd([
            { name: "TryOnU", path: "/" },
            { name: "Ready looks", path: "/looks" },
            { name: collection.h1, path },
          ]),
        ]}
      />
      <section className="tu-container py-10 md:py-14">
        <Link href="/looks" className="text-[14.5px] font-semibold text-sage-deep hover:underline">
          ← All ready looks
        </Link>
        <h1 className="mt-3 max-w-3xl font-display text-[clamp(32px,4.8vw,54px)] leading-[1.05] text-ink">{collection.h1}</h1>
        {collection.intro.map((p) => (
          <p key={p} className="mt-3 max-w-3xl text-[17px] leading-relaxed text-ink-soft">{p}</p>
        ))}
        <p className="mt-3 max-w-3xl text-[15px] text-muted">
          Your photo is used only for your own try-ons: see the{" "}
          <Link href="/photo-policy" className="text-sage-deep underline">photo policy</Link> and{" "}
          <Link href="/privacy" className="text-sage-deep underline">privacy policy</Link>.
        </p>
        <FirstOutfitOffer variant="banner" className="mt-6 max-w-3xl" />
        <div className="mt-8">
          <LookCards looks={looks} />
        </div>
        <div className="mt-12 flex flex-wrap gap-3">
          {others.map((c) => (
            <Link key={c.slug} href={`/looks/${c.slug}`} className="rounded-full border border-line-strong px-4 py-2 text-[15px] font-medium text-ink hover:border-ink/40">
              {c.h1} →
            </Link>
          ))}
          <Link href="/winter-outfit-try-on" className="rounded-full border border-line-strong px-4 py-2 text-[15px] font-medium text-ink hover:border-ink/40">
            Winter outfit ideas →
          </Link>
        </div>
      </section>
    </SiteChrome>
  );
}
