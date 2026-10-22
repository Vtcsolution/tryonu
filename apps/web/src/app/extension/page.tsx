import { ContentPage, SectionTitle, Steps } from "@/components/content/ContentPage";
import { CheckIcon } from "@/components/ui/Icons";
import { JsonLd, breadcrumbJsonLd, faqJsonLd } from "@/components/seo/JsonLd";
import { Button } from "@/components/ui/Button";
import { SITE, pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "TryOnU Browser Extension: Try On Clothes From Any Shop",
  description:
    "Free Chrome and Edge extension: try clothes, shoes and accessories from eBay, AliExpress or any online shop on your own photo. Shops: add products to TryOnU in one click.",
  path: "/extension",
  keywords: ["virtual try on extension", "try on clothes chrome extension", "eBay try on", "AliExpress try on"],
});

// Set these on the server once the extensions are live in the stores; until then people download the zip.
const SHOPPER_STORE_URL = process.env.NEXT_PUBLIC_EXTENSION_SHOPPER_URL || "";
const STORE_STORE_URL = process.env.NEXT_PUBLIC_EXTENSION_STORE_URL || "";

const FAQ = [
  {
    q: "Which shops does the TryOnU extension work on?",
    a: "Any online shop: eBay, AliExpress, brand stores and small shops. Open a product page and click the TryOnU button, or right-click the product picture.",
  },
  {
    q: "What does a try-on from the extension cost?",
    a: "The same as on tryonu.app: it uses your normal TryOnU credits, and if a try-on fails the credits come back automatically.",
  },
  {
    q: "Do I need a TryOnU account?",
    a: "Yes, a free one, with one photo of yourself. The extension connects to your account in one click.",
  },
  {
    q: "What does the store extension do?",
    a: "Shop owners open a product page, their own website or anywhere else, and add that product to their TryOnU store with its name, price and picture filled in. Your plan's product limit applies.",
  },
];

function InstallButton({ storeUrl, zip, label }: { storeUrl: string; zip: string; label: string }) {
  return storeUrl ? (
    <Button href={storeUrl} size="lg" className="w-full">
      {label} <span aria-hidden="true">→</span>
    </Button>
  ) : (
    <a
      href={zip}
      download
      className="tu-press flex min-h-[52px] w-full items-center justify-center rounded-full bg-sage px-6 text-[16px] font-semibold text-white hover:bg-sage-deep"
    >
      Download the extension
    </a>
  );
}

export default function ExtensionPage() {
  const apps = [
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      name: "TryOnU – Try It On",
      applicationCategory: "BrowserApplication",
      operatingSystem: "Chrome, Microsoft Edge",
      description: "Try clothes, shoes and accessories from any online shop on your own photo with AI.",
      url: `${SITE}/extension`,
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
      publisher: { "@id": `${SITE}/#organization` },
    },
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      name: "TryOnU for Stores",
      applicationCategory: "BrowserApplication",
      operatingSystem: "Chrome, Microsoft Edge",
      description: "Add products from any page to your TryOnU store in one click.",
      url: `${SITE}/extension#stores`,
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
      publisher: { "@id": `${SITE}/#organization` },
    },
  ];
  const card = "flex flex-col rounded-[24px] border border-line bg-surface p-6 md:p-8";
  const tick = "flex gap-2.5 text-[15.5px] leading-relaxed text-ink-soft";
  return (
    <ContentPage
      kicker="Browser extension"
      title={
        <>
          Try on clothes from <em>any shop</em>, right in your browser
        </>
      }
      intro="Shopping on eBay, AliExpress or any website? Click the TryOnU button and see the product on your own photo before you buy. Free for Chrome and Microsoft Edge."
    >
      <JsonLd data={[...apps, faqJsonLd(FAQ), breadcrumbJsonLd([{ name: "TryOnU", path: "/" }, { name: "Browser extension", path: "/extension" }])]} />

      <div className="grid gap-5 md:grid-cols-2">
        <div className={card}>
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">For shoppers</p>
          <h2 className="mt-1 font-display text-[28px] text-ink">TryOnU – Try It On</h2>
          <ul className="mt-4 flex-1 space-y-2.5">
            {[
              "Works on eBay, AliExpress and any online shop",
              "One click on the product page, or right-click any product picture",
              "The product goes onto your own TryOnU photo in about a minute",
              "Uses your normal TryOnU credits; failed try-ons are free",
              "Save the look to your TryOnU account",
            ].map((t) => (
              <li key={t} className={tick}>
                <span className="text-sage"><CheckIcon size={16} /></span>
                {t}
              </li>
            ))}
          </ul>
          <div className="mt-6">
            <InstallButton storeUrl={SHOPPER_STORE_URL} zip="/downloads/tryonu-extension-shopper.zip" label="Add to Chrome" />
          </div>
        </div>

        <div id="stores" className={`${card} scroll-mt-24`}>
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">For store owners</p>
          <h2 className="mt-1 font-display text-[28px] text-ink">TryOnU for Stores</h2>
          <ul className="mt-4 flex-1 space-y-2.5">
            {[
              "Add products to your TryOnU store from any page, your own website included",
              "Name, price, currency and pictures filled in for you",
              "Pick the main picture, the category and who it's for",
              "Right-click a product picture to add it",
              "Shows how many products your plan has left",
            ].map((t) => (
              <li key={t} className={tick}>
                <span className="text-sage"><CheckIcon size={16} /></span>
                {t}
              </li>
            ))}
          </ul>
          <div className="mt-6">
            <InstallButton storeUrl={STORE_STORE_URL} zip="/downloads/tryonu-extension-store.zip" label="Add to Chrome" />
          </div>
        </div>
      </div>

      {(!SHOPPER_STORE_URL || !STORE_STORE_URL) && (
        <div className="mt-14 max-w-3xl">
          <SectionTitle sub="One-click install from the Chrome Web Store is coming soon. Until then it takes two minutes:">
            How to install
          </SectionTitle>
          <ol className="space-y-3 text-[16px] leading-relaxed text-ink-soft">
            {[
              <>Download the extension above and <b className="text-ink">unzip</b> it (right-click → Extract all).</>,
              <>
                In Chrome, open <code className="rounded bg-paper-2 px-1.5 py-0.5">chrome://extensions</code> (in Edge:{" "}
                <code className="rounded bg-paper-2 px-1.5 py-0.5">edge://extensions</code>).
              </>,
              <>Turn on <b className="text-ink">Developer mode</b> (top right).</>,
              <>Click <b className="text-ink">Load unpacked</b> and choose the unzipped folder.</>,
              <>The TryOnU page opens: click <b className="text-ink">Connect this browser</b>. Done.</>,
            ].map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sage text-[13px] font-semibold text-white">{i + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
          <p className="mt-3 text-[14px] text-muted">Tip: click the puzzle-piece icon in the toolbar and pin TryOnU, so its button is always visible.</p>
        </div>
      )}

      <div className="mt-14">
        <SectionTitle>How it works</SectionTitle>
        <Steps
          steps={[
            { title: "Install and connect", text: "Add the extension, then connect it to your free TryOnU account in one click." },
            { title: "Open any product", text: "On eBay, AliExpress or any shop, click the TryOnU button, or right-click the product picture." },
            { title: "See it on you", text: "In about a minute you see yourself wearing it. Save the look, then buy from the shop you're on." },
          ]}
        />
      </div>

      <div className="mt-14 max-w-3xl">
        <SectionTitle>Questions</SectionTitle>
        <div className="divide-y divide-line rounded-[22px] border border-line bg-surface">
          {FAQ.map((f) => (
            <div key={f.q} className="px-5 py-4">
              <h3 className="text-[17px] font-semibold text-ink">{f.q}</h3>
              <p className="mt-1.5 text-[15.5px] leading-relaxed text-ink-soft">{f.a}</p>
            </div>
          ))}
        </div>
      </div>
    </ContentPage>
  );
}
