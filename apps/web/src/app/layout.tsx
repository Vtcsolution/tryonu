import type { Metadata, Viewport } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { JsonLd } from "@/components/seo/JsonLd";
import { CORE_KEYWORDS, OWNER, SITE, SITE_DEFINITION, SITE_NAME, SITE_TAGLINE, SOCIAL_LINKS } from "@/lib/seo";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
  display: "swap",
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: {
    default: "TryOnU: AI Virtual Try-On. See Clothes on You Before You Buy",
    template: "%s · TryOnU",
  },
  description:
    "Try real clothes, shoes and accessories on your own photo with AI, then buy from the original store. Whole outfits, an AI stylist, local shops first. Try it free.",
  applicationName: SITE_NAME,
  // added to an iPhone's home screen: opens full screen, named TryOnU
  appleWebApp: { capable: true, title: "TryOnU", statusBarStyle: "default" },
  keywords: CORE_KEYWORDS,
  alternates: { canonical: "/" },
  category: "shopping",
  openGraph: {
    type: "website",
    url: SITE,
    siteName: SITE_NAME,
    title: "TryOnU: try real fashion on you before you buy",
    description: "AI virtual try-on: real products from real stores, on your own photo. Then shop the original store.",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "TryOnU: try real fashion on you before you buy",
    description: "AI virtual try-on: real products from real stores, on your own photo.",
  },
  // site ownership for Google Search Console and Bing Webmaster Tools (public tokens, set on the server)
  verification: {
    ...(process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION ? { google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION } : {}),
    other: {
      // Mitgo (Admitad) affiliate ad-space ownership check; a public token, not a secret
      "mitgo-verification": "794de6ff-f7d7-4405-8164-728c91d75317",
      ...(process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION ? { "msvalidate.01": process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION } : {}),
    },
  },
};

/** Who TryOnU is, for search engines and AI assistants (every page). */
const ORGANIZATION = [
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${SITE}/#organization`,
    name: SITE_NAME,
    legalName: OWNER,
    url: SITE,
    logo: `${SITE}/tryonu-logo-100.png`,
    description: SITE_DEFINITION,
    slogan: SITE_TAGLINE,
    sameAs: SOCIAL_LINKS.map((s) => s.url),
    contactPoint: { "@type": "ContactPoint", contactType: "customer support", url: `${SITE}/contact` },
  },
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE}/#website`,
    name: SITE_NAME,
    url: SITE,
    description: SITE_DEFINITION,
    publisher: { "@id": `${SITE}/#organization` },
    inLanguage: "en",
  },
];

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfaf6" },
    { media: "(prefers-color-scheme: dark)", color: "#141410" },
  ],
  colorScheme: "light dark",
  // phones with a notch or a home bar: the app's bottom tabs keep clear of it
  viewportFit: "cover",
};

/**
 * Runs before first paint so an explicit theme choice (or the OS setting)
 * is applied without a flash. Keep in sync with ThemeToggle's storage key.
 */
const NO_FLASH = `(function(){try{var t=localStorage.getItem('tryonu-theme');if(t==='light'||t==='dark'){document.documentElement.dataset.theme=t;}}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${playfair.variable}`}
      suppressHydrationWarning
    >
      <body className="grain">
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH }} />
        <JsonLd data={ORGANIZATION} />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
