import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { CtaBand, Icon, LooksMarquee, PitchHero, PitchSection, StepFlow, Tiles, mailto } from "@/components/pitch/PitchKit";
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
  const looks = (await publishedLooks()).slice(0, 14);
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
            { big: "Live products", text: "Searched live on eBay, AliExpress, Rakuten and Admitad brand stores." },
            { big: "AI Stylist", text: "Understands plain words in any language and finds real products." },
            { big: "Find the look", text: "Upload a screenshot; it finds each piece in real shops." },
            { big: "Store websites", text: "Shops get their own TryOnU store with try-on, cart and WhatsApp orders." },
            { big: "Try-on API", text: "Brands add a Try it on button to their own website in one line." },
            { big: "Community", text: "Posts, likes, replies, follows, polls and weekly style challenges." },
            { big: "Payments live", text: "Credit packs paid by PayPal today; card checkout prepared." },
          ]}
        />
      </PitchSection>

      <PitchSection kicker="Business model" title="Four ways TryOnU earns." tint>
        <Tiles
          columns={4}
          items={[
            { big: "Shoppers", text: "Credit packs for try-ons. The first outfit is free." },
            { big: "Affiliate", text: "Commission when shoppers buy through the Shop links." },
            { big: "Shops", text: "Monthly plans for their own TryOnU store website." },
            { big: "API", text: "Prepaid try-on packs for brands and developers." },
          ]}
        />
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
