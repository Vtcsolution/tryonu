import type { Metadata } from "next";
import Link from "next/link";
import { ContentPage, LegalBody } from "@/components/content/ContentPage";

export const metadata: Metadata = {
  title: "Affiliate disclosure",
  description: "How TryOnU earns a small commission from shop links, why you always pay the same price, and how products are chosen for you.",
  alternates: { canonical: "/affiliate-disclosure" },
};

export default function AffiliateDisclosurePage() {
  return (
    <ContentPage kicker="Legal" title="Affiliate disclosure" intro="How TryOnU earns money, in plain words." narrow>
      <LegalBody updated="16 October 2026">
        <h2>Shop links may earn us a commission</h2>
        <p>
          Many &quot;Shop now&quot; links on TryOnU are affiliate links. When you buy something after clicking one, the store or
          marketplace may pay TryOnU a small commission. <strong>You pay the same price</strong> whether or not you use our link.
        </p>
        <p>
          We work with affiliate programmes of marketplaces and networks such as eBay, AliExpress, Admitad and Amazon. As an Amazon
          Associate, TryOnU earns from qualifying purchases.
        </p>

        <h2>It doesn&apos;t decide what you see</h2>
        <p>
          Products are chosen to match what you asked for, your style and your country. Stores that sell on TryOnU are shown first when
          their products match your request equally well; a store&apos;s plan never pushes a poor match above a good one.
        </p>

        <h2>We are not the seller</h2>
        <p>
          TryOnU is an independent service and is not owned by, or acting for, the stores and marketplaces shown. When you buy, you buy
          from that store, under its own prices, delivery, returns and customer service. Prices and stock can change after we show them,
          so check the store&apos;s page before you pay.
        </p>

        <h2>Other ways we earn</h2>
        <ul>
          <li>Credit packs that shoppers buy for try-ons.</li>
          <li>Plans for stores that sell on TryOnU.</li>
          <li>Prepaid credits for developers using the try-on API.</li>
        </ul>

        <p className="!mt-10">
          Questions? <Link href="/contact">Contact us</Link>.
        </p>
      </LegalBody>
    </ContentPage>
  );
}
