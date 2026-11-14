import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { CtaBand, Icon, LooksMarquee, PitchHero, PitchSection, StepFlow, Tiles, mailto } from "@/components/pitch/PitchKit";
import { InvestCalculator } from "@/components/pitch/InvestCalculator";
import { Reveal } from "@/components/ui/Reveal";
import { serverFetch } from "@/lib/api/server";
import type { CreditPackage, StorePlan } from "@/lib/api/types";
import { publishedLooks } from "@/lib/looks";

export const metadata: Metadata = {
  title: { absolute: "Invest in TryOnU: AI Try-On for Online Fashion" },
  description: "TryOnU puts real clothes from real stores on a shopper's own photo, then they buy from the store. Live today.",
  // shared by direct message, not a search page
  robots: { index: false, follow: true },
  openGraph: {
    title: "Invest in TryOnU",
    description: "AI try-on for online fashion: see it on you, then buy. Live at tryonu.app.",
    images: [{ url: "https://tryonu.app/opengraph-image" }],
  },
};

export const revalidate = 600;

/** /invest: the investor pitch, for a link sent by message. Short, visual, true. */
export default async function InvestPage() {
  const [allLooks, packs, plans, devPacks] = await Promise.all([
    publishedLooks(),
    serverFetch<CreditPackage[]>("/api/v1/credits/packages", { revalidateSeconds: 600 }),
    serverFetch<StorePlan[]>("/api/v1/stores/plans", { revalidateSeconds: 600 }),
    serverFetch<{ name: string; tryons: number; price_cents: number; is_active: boolean }[]>("/api/v1/developers/packs", { revalidateSeconds: 600 }),
  ]);
  const looks = allLooks.slice(0, 14);
  const shopperPacks = (packs ?? []).filter((p) => !p.new_members_only).sort((a, b) => a.price_cents - b.price_cents);
  const storePlans = (plans ?? []).filter((p) => p.is_active).sort((a, b) => a.price_cents - b.price_cents);
  const apiPacks = (devPacks ?? []).filter((p) => p.is_active).sort((a, b) => a.price_cents - b.price_cents);
  // the calculator's averages: the middle shopper pack, most stores on the smaller plans, the middle API pack
  const mid = <T,>(list: T[]) => list[Math.floor((list.length - 1) / 2)];
  const shopperSpend = shopperPacks.length ? mid(shopperPacks).price_cents / 100 : 12.99;
  const planPrices = storePlans.map((p) => p.price_cents / 100);
  const storePlan = planPrices.length
    ? Math.round(planPrices[0] * 0.6 + (planPrices[1] ?? planPrices[0]) * 0.3 + (planPrices[planPrices.length - 1] ?? planPrices[0]) * 0.1)
    : 30;
  const apiPack = apiPacks.length ? mid(apiPacks).price_cents / 100 : 150;
  const talk = mailto("Investing in TryOnU");
  return (
    <SiteChrome>
      <PitchHero
        kicker="For investors"
        title={
          <>
            Shoppers can&apos;t try clothes on online. <em className="text-sage-deep">TryOnU lets them.</em>
          </>
        }
        sub="One photo. Real clothes from real stores. The shopper sees the whole outfit on themselves in about a minute, then buys it. Live today."
        primary={{ label: "Talk to the founder", href: talk }}
        secondary={{ label: "Try it yourself", href: "/try" }}
      />

      <PitchSection kicker="The problem" title="Online fashion has a returns problem." tint>
        <Tiles
          items={[
            { big: "19.3%", text: "of online sales were returned in 2025 (NRF and Happy Returns)." },
            { big: "1 in 4", text: "clothes bought online are sent back (Coresight Research)." },
            { big: "Guesswork", text: "Shoppers can't see colour, shape or style on themselves, so they hesitate, or buy several sizes and return most." },
          ]}
        />
        <p className="mt-6 max-w-3xl text-[17px] leading-relaxed text-ink-soft">
          In January 2025 Amazon ended Prime Try Before You Buy. Shoppers still need a way to see clothes on themselves before
          buying. That is what TryOnU does.
        </p>
      </PitchSection>

      <PitchSection kicker="The product" title="See it on you, then buy it.">
        <StepFlow
          steps={[
            { title: "Add one photo", text: "Once. Private to the shopper.", icon: Icon.photo },
            { title: "Pick or describe", text: "A product, a whole outfit, or plain words to the AI Stylist.", icon: Icon.hanger },
            { title: "See it, buy it", text: "The full look on you in about a minute. Every piece links to its store.", icon: Icon.bag },
          ]}
        />
      </PitchSection>

      <PitchSection kicker="Real results" title="Looks made with TryOnU." tint>
        <LooksMarquee looks={looks} />
      </PitchSection>

      <PitchSection kicker="Built and live" title="Not a prototype. A working platform.">
        <Tiles
          columns={4}
          items={[
            { big: "Whole outfits", text: "Up to five real products on one photo, in one picture." },
            { big: "Live products", text: "Searched live on eBay, AliExpress and brand stores." },
            { big: "AI Stylist", text: "Understands plain words in any language and finds real products." },
            { big: "Find the look", text: "Upload a screenshot; it finds each piece in real shops." },
            { big: "Store websites", text: "Shops get their own TryOnU store with try-on, cart and WhatsApp orders." },
            { big: "Try-on API", text: "Brands add a Try it on button to their own website in one line." },
            { big: "Community", text: "Posts, likes, replies, follows, polls and weekly style challenges." },
            { big: "Payments live", text: "Credit packs paid by PayPal today; card checkout prepared." },
          ]}
        />
      </PitchSection>

      <PitchSection kicker="How TryOnU earns" title="Four ways the money comes in." tint>
        <div className="grid gap-4 md:grid-cols-2">
          <EarnCard
            color="#3d8547"
            title="Shoppers"
            line="Credit packs for try-ons. No subscription. The first outfit is free, to get them started."
            prices={shopperPacks.map((p) => `${money(p.price_cents)} for ${p.credits} credits`)}
          />
          <EarnCard
            color="#c9a13b"
            title="Stores"
            line="Fashion shops pay monthly for their own TryOnU store website with try-on, cart and WhatsApp orders."
            prices={storePlans.map((p) => `${p.name}: ${money(p.price_cents)} a month, ${p.product_limit} products`)}
          />
          <EarnCard
            color="#4a7fb5"
            title="Try-on API"
            line="Brands and online stores buy prepaid try-on packs to add a Try it on button to their own websites."
            prices={apiPacks.map((p) => `${p.name}: ${money(p.price_cents)} for ${p.tryons} try-ons`)}
          />
          <EarnCard
            color="#b4483a"
            title="Affiliate"
            line="Every product links to the store that sells it. When a shopper buys, the store pays TryOnU a commission on the sale."
            prices={["A share of every sale through TryOnU's shop links", "Typically a few percent, set by each store's programme"]}
          />
        </div>
      </PitchSection>

      <PitchSection kicker="Our 2027 goal" title="How the revenue adds up.">
        <InvestCalculator shopperSpend={shopperSpend} storePlan={storePlan} apiPack={apiPack} />
      </PitchSection>

      <PitchSection kicker="Where we're going" title="Next: the USA, UK, Canada, Australia and the Gulf.">
        <Tiles
          items={[
            { big: "Amazon", text: "Amazon product search, as soon as Amazon's API access is approved." },
            { big: "Shopify app", text: "One-click try-on for Shopify stores, after the widget that works today." },
            { big: "Phone apps", text: "App Store and Google Play, after the installable web app live today." },
          ]}
        />
      </PitchSection>

      <PitchSection kicker="The founder" title="Zia Shafique, founder of TryOnU." tint>
        <p className="max-w-3xl text-[18px] leading-relaxed text-ink-soft">
          Built TryOnU end to end, from the AI try-on pipeline and live product search to payments, store websites, the API,
          the community and the hosting. TryOnU is a product of Greatodeal AI Automation Solutions.
        </p>
      </PitchSection>

      <CtaBand
        title="Let's talk about TryOnU."
        sub="A short call or a demo on your own photo. Reply to the message you got, or write to us."
        primary={{ label: "Email the founder", href: talk }}
        secondary={{ label: "Try it yourself", href: "/try" }}
      />
    </SiteChrome>
  );
}

const money = (cents: number) => `$${(cents / 100).toFixed(2).replace(/\.00$/, "")}`;

/** One way TryOnU earns: a colour, a big name, one sentence and its live prices. */
function EarnCard({ color, title, line, prices }: { color: string; title: string; line: string; prices: string[] }) {
  return (
    <Reveal className="relative overflow-hidden rounded-[26px] border border-line bg-surface p-6 pl-8 transition-shadow hover:shadow-lift">
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-2" style={{ backgroundColor: color }} />
      <p className="font-display text-[32px] leading-none text-ink">{title}</p>
      <p className="mt-3 text-[16.5px] leading-relaxed text-ink-soft">{line}</p>
      <ul className="mt-4 space-y-2">
        {prices.map((p) => (
          <li key={p} className="flex items-center gap-2 text-[15.5px] font-semibold text-ink">
            <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
            {p}
          </li>
        ))}
      </ul>
    </Reveal>
  );
}
