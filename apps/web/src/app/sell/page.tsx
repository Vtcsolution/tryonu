import type { Metadata } from "next";
import { ContentPage, InfoCard, SectionTitle, cardGrid, Steps } from "@/components/content/ContentPage";
import { formatPrice } from "@/components/try/shop";
import { Button } from "@/components/ui/Button";
import { serverFetch } from "@/lib/api/server";
import type { StorePlan } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Sell on TryOnU",
  description: "Open a store on TryOnU: your products are recommended to shoppers near you, and shoppers can try them on before they buy.",
};

const BENEFITS: { title: string; text: string }[] = [
  {
    title: "Recommended first, near you",
    text: "When a shopper asks for something you sell, your products come first, ahead of the big marketplaces, for shoppers in the areas you deliver to.",
  },
  {
    title: "Shoppers try before they buy",
    text: "Shoppers see your products on their own photo. Fewer doubts mean more confident orders and fewer returns.",
  },
  {
    title: "Feature your best products",
    text: "Pick the products you want shown most. Higher plans feature more products and rank first when matches are equally good.",
  },
  {
    title: "Free try-ons for your shoppers",
    text: "Plans can include try-ons you pay for, so shoppers try your products free. With their consent, you see the try-on pictures.",
  },
  {
    title: "Deliver where you want",
    text: "Choose your country or the areas you deliver to. Shoppers elsewhere aren't shown products they can't receive.",
  },
  {
    title: "Simple dashboard",
    text: "Add products one by one or upload a CSV, see views and try-ons, and manage your plan in one place.",
  },
];

export default async function SellPage() {
  const plans = await serverFetch<StorePlan[]>("/api/v1/stores/plans", { revalidateSeconds: 300 });
  return (
    <ContentPage
      kicker="For stores"
      title={
        <>
          Sell on <em>TryOnU</em>
        </>
      }
      intro="Put your clothes, shoes and accessories in front of shoppers who are ready to buy, and let them see your products on themselves first."
    >
      <div className="flex flex-wrap gap-3">
        <Button href="/business/sign-up" size="lg">Open your store →</Button>
        <Button href="/business" size="lg" variant="outline">Go to my store dashboard</Button>
      </div>

      <div className="mt-14">
        <SectionTitle>Why stores choose TryOnU</SectionTitle>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {BENEFITS.map((b) => (
            <InfoCard key={b.title} title={b.title}>
              {b.text}
            </InfoCard>
          ))}
        </div>
      </div>

      <div className="mt-16">
        <SectionTitle>Start in three steps</SectionTitle>
        <Steps
          steps={[
            { title: "Create your store", text: "Sign up with your store's name, country and contact details." },
            { title: "Choose a plan", text: "Pay securely with PayPal. We review new stores before they go live." },
            { title: "Add your products", text: "Add photos, prices and links, or upload a CSV. Shoppers start seeing them right away." },
          ]}
        />
      </div>

      {plans && plans.length > 0 && (
        <div className="mt-16">
          <SectionTitle sub="Each plan runs for a fixed period; renew whenever you like.">Store plans</SectionTitle>
          <div className={cardGrid(plans.length)}>
            {plans.map((plan) => (
              <InfoCard
                key={plan.id}
                title={plan.name}
                footer={
                  <Button href="/business/sign-up" size="md" variant="outline" className="w-full">
                    Choose {plan.name}
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
                  <li>{plan.tryon_credits > 0 ? `${plan.tryon_credits.toLocaleString()} free try-ons for shoppers` : "No included try-ons"}</li>
                </ul>
              </InfoCard>
            ))}
          </div>
        </div>
      )}

      <div className="mt-16 flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-line bg-surface p-6 md:p-8">
        <div>
          <p className="font-display text-[26px] text-ink">Have questions before you start?</p>
          <p className="mt-1 text-[16px] text-ink-soft">Tell us about your store and we&apos;ll help you set it up.</p>
        </div>
        <Button href="/contact?topic=store" size="lg" variant="outline">Talk to us</Button>
      </div>
    </ContentPage>
  );
}
