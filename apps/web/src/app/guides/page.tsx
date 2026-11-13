import Link from "next/link";
import { ContentPage, SectionTitle } from "@/components/content/ContentPage";
import { JsonLd, breadcrumbJsonLd } from "@/components/seo/JsonLd";
import { GUIDES } from "@/lib/guides";
import { SITE, pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Guides: Buying Clothes Online With Fewer Returns",
  description:
    "Practical guides to buying clothes online: trying them on your own photo first, sizing on eBay and AliExpress, avoiding returns, and dressing for snow.",
  path: "/guides",
  keywords: ["online clothes shopping guide", "virtual try on guide"],
});

/** /guides: every article, shoppers first. */
export default function GuidesIndex() {
  const groups: [string, typeof GUIDES][] = [
    ["For shoppers", GUIDES.filter((g) => g.audience === "shopper")],
    ["For shops and brands", GUIDES.filter((g) => g.audience === "business")],
  ];
  return (
    <ContentPage
      kicker="Guides"
      title="Guides to buying clothes online"
      intro="Short, practical guides: how to see clothes on yourself before you order, how to judge sizes from eBay and AliExpress, how to avoid returns, and what to wear when the weather turns."
    >
      <JsonLd
        data={[
          {
            "@context": "https://schema.org",
            "@type": "ItemList",
            name: "TryOnU guides",
            itemListElement: GUIDES.map((g, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE}/guides/${g.slug}`, name: g.h1 })),
          },
          breadcrumbJsonLd([
            { name: "TryOnU", path: "/" },
            { name: "Guides", path: "/guides" },
          ]),
        ]}
      />
      {groups.map(([title, list]) => (
        <div key={title} className="mt-10">
          <SectionTitle>{title}</SectionTitle>
          <ul className="grid gap-4 md:grid-cols-2">
            {list.map((g) => (
              <li key={g.slug}>
                <Link href={`/guides/${g.slug}`} className="group block h-full rounded-[22px] border border-line bg-surface p-5 hover:border-sage">
                  <span className="block font-display text-[22px] leading-snug text-ink group-hover:text-sage-deep">{g.h1}</span>
                  <span className="mt-2 block text-[15.5px] leading-relaxed text-ink-soft">{g.description}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </ContentPage>
  );
}
