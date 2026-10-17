import { ContentPage, InfoCard, SectionTitle, Steps } from "@/components/content/ContentPage";
import { Button } from "@/components/ui/Button";
import { SITE_DEFINITION, pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "About TryOnU: AI Virtual Try-On for Shoppers, Shops & Developers",
  description:
    "TryOnU lets anyone see real products on their own photo before they buy, helps local shops reach shoppers, and gives developers a try-on API.",
  path: "/about",
  keywords: ["about TryOnU", "TryOnU company"],
});

export default function AboutPage() {
  return (
    <ContentPage
      kicker="About TryOnU"
      title={
        <>
          See it on <em>you</em> before you buy it
        </>
      }
      intro="Buying clothes online is guesswork: a product looks great on a model, then arrives and looks different on you. TryOnU puts real products from real stores on your own photo, so you can decide with confidence and shop from the original store."
    >
      <p className="mb-12 max-w-3xl text-[18px] leading-relaxed text-ink">{SITE_DEFINITION}</p>

      <SectionTitle sub="One platform, three kinds of people.">Who TryOnU is for</SectionTitle>
      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard title="Shoppers" footer={<Button href="/try" size="md">Try it now →</Button>}>
          Upload your photo once. Try a single product or a whole outfit from eBay, AliExpress, brand stores and local shops,
          save your looks and share them with friends.
        </InfoCard>
        <InfoCard title="Stores" footer={<Button href="/sell" size="md" variant="outline">Sell on TryOnU</Button>}>
          Open a store on TryOnU. Your products are recommended first to shoppers in the areas you deliver to, and shoppers can
          try them on before they buy.
        </InfoCard>
        <InfoCard title="Developers" footer={<Button href="/developers" size="md" variant="outline">Try-on API</Button>}>
          Add virtual try-on to your own app or online shop with our API, a one-line website widget, or the WordPress and Shopify
          setup. Pay only for the try-ons you use.
        </InfoCard>
      </div>

      <div className="mt-16">
        <SectionTitle>How it works</SectionTitle>
        <Steps
          steps={[
            { title: "Add your photo", text: "A clear photo of you, standing and facing the camera. You do this once." },
            { title: "Pick products", text: "Search, ask the AI Stylist in your own words, or build an outfit from several stores." },
            { title: "See it on you", text: "In under a minute you see yourself wearing it, with a link to buy each piece." },
          ]}
        />
      </div>

      <div className="mt-16">
        <SectionTitle>What we stand for</SectionTitle>
        <div className="grid gap-4 md:grid-cols-3">
          <InfoCard title="Your photos stay yours">
            Your photos are used only to make your try-ons. We never sell them, and nothing is shared unless you choose to share it.{" "}
            <a href="/photo-policy" className="text-sage-deep underline">Photo &amp; data policy</a>
          </InfoCard>
          <InfoCard title="Real products, real stores">
            Every product comes from a real store with a real price. You buy from that store, and TryOnU never sells you a product
            directly.
          </InfoCard>
          <InfoCard title="Honest previews">
            Try-on pictures are made with AI. They are a strong guide, but fit, size and colour can differ, so always check the
            store&apos;s size chart.
          </InfoCard>
        </div>
      </div>

      <div className="mt-16 flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-line bg-surface p-6 md:p-8">
        <div>
          <p className="font-display text-[26px] text-ink">Questions, ideas or partnerships?</p>
          <p className="mt-1 text-[16px] text-ink-soft">We read every message.</p>
        </div>
        <Button href="/contact" size="lg">Contact us</Button>
      </div>
    </ContentPage>
  );
}
