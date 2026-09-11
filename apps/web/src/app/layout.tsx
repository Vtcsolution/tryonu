import type { Metadata, Viewport } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

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

const SITE = "https://tryonu.ai";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: {
    default: "TryOnU — Try It. See You. Shop It.",
    template: "%s · TryOnU",
  },
  description:
    "TryOnU is an AI-powered virtual fashion shopping experience. Try real products from top retailers on your own photos, then shop from the original store.",
  keywords: [
    "virtual try-on",
    "AI fashion",
    "TryOnU",
    "online shopping",
    "affiliate fashion",
  ],
  openGraph: {
    type: "website",
    url: SITE,
    title: "TryOnU — Try It. See You. Shop It.",
    description:
      "Try real fashion on you before you buy. AI virtual try-on across top marketplaces.",
    siteName: "TryOnU",
  },
  twitter: {
    card: "summary_large_image",
    title: "TryOnU — Try It. See You. Shop It.",
    description: "Try real fashion on you before you buy.",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfaf6" },
    { media: "(prefers-color-scheme: dark)", color: "#141410" },
  ],
  colorScheme: "light dark",
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
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
