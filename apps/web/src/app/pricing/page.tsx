import type { Metadata } from "next";
import Link from "next/link";
import { ContentPage, InfoCard, SectionTitle, cardGrid } from "@/components/content/ContentPage";
import { formatPrice } from "@/components/try/shop";
import { Button } from "@/components/ui/Button";
import { serverFetch } from "@/lib/api/server";
import type { CreditPackage, StorePlan } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Simple credit packs for try-ons, plans for stores, and pay-as-you-go credits for the try-on API.",
};

export default async function PricingPage() {
  const [packs, cost, plans] = await Promise.all([
    serverFetch<CreditPackage[]>("/api/v1/credits/packages", { revalidateSeconds: 300 }),
    serverFetch<{ tryon_cost: number; outfit_tryon_cost: number }>("/api/v1/credits/pricing", { revalidateSeconds: 300 }),
    serverFetch<StorePlan[]>("/api/v1/stores/plans", { revalidateSeconds: 300 }),
  ]);
  const sortedPacks = [...(packs ?? [])].sort((a, b) => a.price_cents - b.price_cents);
  const perLook = cost?.outfit_tryon_cost ?? null;

  return (
    <ContentPage
      kicker="Pricing"
      title="Simple, pay-as-you-go pricing"
      intro="No subscription. Buy credits when you need them and use them for try-ons. If a try-on fails, its credits come back automatically."
    >
      <SectionTitle
        sub={
          cost
            ? `One product costs ${cost.tryon_cost} credit${cost.tryon_cost === 1 ? "" : "s"}. A complete outfit look costs ${cost.outfit_tryon_cost} credits.`
            : undefined
        }
      >
        Credits for shoppers
      </SectionTitle>
      {sortedPacks.length > 0 ? (
        <div className={cardGrid(sortedPacks.length)}>
          {sortedPacks.map((p, i) => (
            <div
              key={p.id}
              className={`flex flex-col rounded-[22px] border bg-surface p-6 ${
                i === 1 && sortedPacks.length > 2 ? "border-sage ring-2 ring-sage/25" : "border-line"
              }`}
            >
              {/* every card keeps this row, so names, prices and buttons line up across cards */}
              <span
                aria-hidden={!(i === 1 && sortedPacks.length > 2)}
                className={`mb-2 self-start rounded-full bg-sage px-2.5 py-0.5 text-[12px] font-semibold text-white ${
                  i === 1 && sortedPacks.length > 2 ? "" : "hidden md:inline-block md:invisible"
                }`}
              >
                Most popular
              </span>
              <p className="text-[18px] font-semibold text-ink">{p.name}</p>
              <p className="mt-2 font-display text-[40px] leading-none text-ink">{formatPrice(p.price_cents, p.currency)}</p>
              <p className="mt-2 text-[15.5px] text-ink-soft">{p.credits.toLocaleString()} credits</p>
              {perLook ? (
                <p className="text-[14px] text-muted">about {Math.floor(p.credits / perLook)} outfit looks</p>
              ) : null}
              <div className="mt-auto pt-5">
                <Button href="/credits" size="md" variant={i === 1 && sortedPacks.length > 2 ? "primary" : "outline"} className="w-full">
                  Buy credits
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[16px] text-muted">
          Credit packs are shown on the <Link href="/credits" className="text-sage-deep underline">credits page</Link>.
        </p>
      )}
      <p className="mt-4 text-[14px] text-muted">
        Payments are processed securely by PayPal (PayPal account or card). You can also{" "}
        <Link href="/earn" className="text-sage-deep underline">earn free credits by inviting friends</Link>.
      </p>

      {plans && plans.length > 0 && (
        <div className="mt-16">
          <SectionTitle sub="Sell on TryOnU: your products are recommended first to shoppers in the areas you deliver to.">
            Plans for stores
          </SectionTitle>
          <div className={cardGrid(plans.length)}>
            {plans.map((plan) => (
              <InfoCard
                key={plan.id}
                title={plan.name}
                footer={
                  <Button href="/business/sign-up" size="md" variant="outline" className="w-full">
                    Open a store
                  </Button>
                }
              >
                <p className="font-display text-[34px] leading-none text-ink">
                  {plan.price_cents > 0 ? formatPrice(plan.price_cents, plan.currency) : "Free"}
                </p>
                <p className="mt-1 text-[14px] text-muted">per {plan.duration_days} days</p>
                <ul className="mt-4 space-y-1.5 text-[15px]">
                  <li>Up to {plan.product_limit.toLocaleString()} products</li>
                  <li>{plan.featured_limit} featured products</li>
                  <li>{plan.tryon_credits > 0 ? `${plan.tryon_credits.toLocaleString()} free try-ons for your shoppers` : "Shoppers try on with their own credits"}</li>
                </ul>
              </InfoCard>
            ))}
          </div>
        </div>
      )}

      <div className="mt-16">
        <SectionTitle>For developers</SectionTitle>
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-line bg-surface p-6 md:p-8">
          <p className="max-w-2xl text-[16px] leading-relaxed text-ink-soft">
            Add try-on to your app or online shop with the API, the website widget, or the WordPress and Shopify setup. Prepaid
            credit packs: 1 credit is 1 try-on, a failed try-on is free, and credits never expire.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button href="/developers" size="md">See API pricing</Button>
            <Button href="/developers/docs" size="md" variant="outline">Read the docs</Button>
          </div>
        </div>
      </div>
    </ContentPage>
  );
}
