import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { BigButton, CtaBand, Icon, PitchHero, PitchSection, StepFlow, Tiles, mailto } from "@/components/pitch/PitchKit";
import { Reveal } from "@/components/ui/Reveal";
import { formatPrice } from "@/components/try/shop";
import { serverFetch } from "@/lib/api/server";

export const metadata: Metadata = {
  title: { absolute: "Add AI Try-On to Your Store in One Line | TryOnU API" },
  description: "Shoppers see your product on their own photo before they buy. A one-line widget for Shopify, WooCommerce and any site, or a REST API.",
  robots: { index: false, follow: true },
  openGraph: {
    title: "Add AI try-on to your store in one line",
    description: "TryOnU's try-on widget and API for fashion stores and apps.",
    images: [{ url: "https://tryonu.app/opengraph-image" }],
  },
};

export const revalidate = 600;

type Pack = { id: string; name: string; tryons: number; price_cents: number; currency: string; is_active: boolean };

const SNIPPET = `<script src="https://tryonu.app/widget.js" data-key="YOUR_KEY" defer></script>
<button data-tryonu-garment="https://your-shop.com/coat.jpg"
        data-tryonu-name="Camel wool coat"></button>`;

/** /try-on-api: the pitch for companies, developers and marketing teams, sent by message. */
export default async function TryOnApiPage() {
  const packs = ((await serverFetch<Pack[]>("/api/v1/developers/packs", { revalidateSeconds: 600 })) ?? [])
    .filter((p) => p.is_active)
    .sort((a, b) => a.price_cents - b.price_cents);
  const talk = mailto("TryOnU API for our store");
  return (
    <SiteChrome>
      <PitchHero
        kicker="Try-on API"
        title={
          <>
            Add AI try-on to your store <em className="text-sage-deep">in one line.</em>
          </>
        }
        sub="Your shoppers see your product on their own photo, right on your product page. Confident shoppers buy, and keep what they buy."
        primary={{ label: "Get your key", href: "/developers/sign-up" }}
        secondary={{ label: "Talk to us", href: talk }}
        look="men"
      />

      <PitchSection kicker="The whole setup" title="Copy. Paste. Done." tint>
        <Reveal className="overflow-hidden rounded-[22px] border border-line bg-[#0f1411] shadow-lift">
          <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-3">
            <span className="h-3 w-3 rounded-full bg-[#e46a5a]" />
            <span className="h-3 w-3 rounded-full bg-[#e6b84a]" />
            <span className="h-3 w-3 rounded-full bg-[#5fae6a]" />
            <span className="ml-3 text-[13px] text-white/60">your product page</span>
          </div>
          <pre className="overflow-x-auto p-5 text-[14.5px] leading-relaxed text-[#cfe8c9]">
            <code>{SNIPPET}</code>
          </pre>
        </Reveal>
        <p className="mt-4 text-[16px] text-ink-soft">
          A <b>Try it on</b> button appears. The shopper adds a photo and sees your product on themselves. Leave the photo link
          empty and it uses the page&apos;s main picture.
        </p>
      </PitchSection>

      <PitchSection kicker="How it works" title="From key to try-on in minutes.">
        <StepFlow
          steps={[
            { title: "Get a key", text: "Sign up and create a website key. It only works on your domain.", icon: Icon.code },
            { title: "Add the button", text: "Paste one line, use the Shopify block or the WordPress plugin.", icon: Icon.store },
            { title: "Shoppers try on", text: "They see your product on their own photo, then add it to the cart.", icon: Icon.spark },
          ]}
        />
      </PitchSection>

      <PitchSection kicker="Works with" title="Your platform, as it is." tint>
        <Tiles
          columns={4}
          items={[
            { big: "Shopify", text: "A Custom Liquid block in your theme. No app to install." },
            { big: "WooCommerce", text: "The TryOnU WordPress plugin." },
            { big: "Any website", text: "The one-line widget above." },
            { big: "REST API", text: "Send a person photo and a product photo, get the try-on back." },
          ]}
        />
      </PitchSection>

      <PitchSection kicker="Fair pricing" title="Pay only for the try-ons you use.">
        {packs.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {packs.map((p) => (
              <div key={p.id} className="rounded-[24px] border border-line bg-surface p-6">
                <p className="text-[15px] font-bold uppercase tracking-[0.1em] text-sage-deep">{p.name}</p>
                <p className="mt-2 font-display text-[40px] leading-none text-ink">{formatPrice(p.price_cents, p.currency).replace(/\.00$/, "")}</p>
                <p className="mt-3 text-[16px] text-ink-soft">
                  {p.tryons} try-ons · {formatPrice(Math.round(p.price_cents / p.tryons), p.currency)} each
                </p>
              </div>
            ))}
          </div>
        )}
        <div className="mt-6">
          <Tiles
            items={[
              { big: "Failed? Free.", text: "A try-on that fails gives its credit back." },
              { big: "No expiry", text: "Credits never expire. No subscription." },
              { big: "Safe keys", text: "Website keys only work on the domains you add." },
            ]}
          />
        </div>
        <div className="mt-8 flex flex-wrap gap-3">
          <BigButton href="/developers/sign-up">Get your key</BigButton>
          <BigButton href="/developers/docs" outline>
            Read the docs
          </BigButton>
        </div>
      </PitchSection>

      <CtaBand
        title="Give your shoppers a fitting room."
        sub="Set it up today, or ask us to help your team with the first products."
        primary={{ label: "Get your key", href: "/developers/sign-up" }}
        secondary={{ label: "Email us", href: talk }}
      />
    </SiteChrome>
  );
}
