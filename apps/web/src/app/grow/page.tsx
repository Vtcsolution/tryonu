import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { BigButton, CtaBand, Icon, LooksMarquee, PitchHero, PitchSection, StepFlow, Tiles, mailto } from "@/components/pitch/PitchKit";
import { formatPrice } from "@/components/try/shop";
import { serverFetch } from "@/lib/api/server";
import type { StorePlan } from "@/lib/api/types";
import { publishedLooks } from "@/lib/looks";

export const metadata: Metadata = {
  title: { absolute: "Sell More Clothes With AI Try-On | TryOnU for Shops" },
  description: "Let shoppers see your clothes on their own photo before they buy: your own store website with try-on, or a Try it on button on your site.",
  robots: { index: false, follow: true },
  openGraph: {
    title: "Sell more clothes with AI try-on",
    description: "Your own store with AI try-on, cart and WhatsApp orders. From TryOnU.",
    images: [{ url: "https://tryonu.app/opengraph-image" }],
  },
};

export const revalidate = 600;

/** /grow: the pitch for shop owners, brands and their teams, sent by message. */
export default async function GrowPage() {
  const [looks, plans] = await Promise.all([
    publishedLooks(),
    serverFetch<StorePlan[]>("/api/v1/stores/plans", { revalidateSeconds: 600 }),
  ]);
  const active = (plans ?? []).filter((p) => p.is_active).sort((a, b) => a.price_cents - b.price_cents);
  const talk = mailto("My shop on TryOnU");
  return (
    <SiteChrome>
      <PitchHero
        kicker="For shops and brands"
        title={
          <>
            Let shoppers see your clothes <em className="text-sage-deep">on themselves.</em>
          </>
        }
        sub="When a shopper sees your coat on their own photo, they stop guessing. Your own store with AI try-on, a cart and WhatsApp orders, ready today."
        primary={{ label: "Open your store", href: "/business/sign-up" }}
        secondary={{ label: "Talk to us", href: talk }}
        look="women"
      />

      <PitchSection kicker="How it works" title="Three steps. No developer needed." tint>
        <StepFlow
          steps={[
            { title: "Add your products", text: "One by one, or upload a spreadsheet.", icon: Icon.store },
            { title: "Shoppers try them on", text: "On their own photo, one product or several together.", icon: Icon.spark },
            { title: "Orders come in", text: "By email, with a ready WhatsApp message from the customer.", icon: Icon.chat },
          ]}
        />
      </PitchSection>

      <PitchSection kicker="What you get" title="Everything a fashion shop needs to sell online.">
        <Tiles
          items={[
            { big: "Your own website", text: "tryonu.app/your-shop, with your logo, products and product pages." },
            { big: "Try it on", text: "On every product, and several products together in one look." },
            { big: "Cart and checkout", text: "Customers order in a few taps. You confirm delivery and payment your way." },
            { big: "WhatsApp built in", text: "A WhatsApp button on every page, and orders ready to send to you." },
            { big: "See their try-ons", text: "Your dashboard shows the pictures customers made with your products." },
            { big: "Found by shoppers", text: "Your products are recommended to TryOnU shoppers in the areas you deliver to." },
          ]}
        />
      </PitchSection>

      {active.length > 0 && (
        <PitchSection kicker="Plans" title="Simple monthly plans." tint>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {active.map((p) => (
              <div key={p.id} className="rounded-[24px] border border-line bg-surface p-6">
                <p className="text-[15px] font-bold uppercase tracking-[0.1em] text-sage-deep">{p.name}</p>
                <p className="mt-2 font-display text-[40px] leading-none text-ink">
                  {formatPrice(p.price_cents, p.currency).replace(/\.00$/, "")}
                  <span className="text-[17px] text-muted"> / {p.duration_days} days</span>
                </p>
                <p className="mt-3 text-[16px] text-ink-soft">Up to {p.product_limit} products</p>
              </div>
            ))}
          </div>
          <div className="mt-8">
            <BigButton href="/business/sign-up">Open your store</BigButton>
          </div>
        </PitchSection>
      )}

      <PitchSection kicker="Real results" title="What your products look like on shoppers.">
        <LooksMarquee looks={looks.slice(0, 14)} />
      </PitchSection>

      <PitchSection kicker="Already have a website?" title="Add a Try it on button to it." tint>
        <Tiles
          items={[
            { big: "Shopify", text: "Paste a short block into your theme. No app needed." },
            { big: "WordPress", text: "Install the WooCommerce plugin and add your key." },
            { big: "Any website", text: "One line of code, or our API for custom shops." },
          ]}
        />
        <div className="mt-8">
          <BigButton href="/try-on-api" outline>
            See how it works
          </BigButton>
        </div>
      </PitchSection>

      <CtaBand
        title="Start selling with try-on this week."
        sub="Open your store in minutes, or ask us anything first."
        primary={{ label: "Open your store", href: "/business/sign-up" }}
        secondary={{ label: "Email us", href: talk }}
      />
    </SiteChrome>
  );
}
