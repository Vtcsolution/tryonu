import type { MetadataRoute } from "next";
import { SITE } from "@/lib/seo";

/** Personal pages (accounts, payments, dashboards) stay out of search;
 * everything public is open to search engines and AI assistants alike. */
const PRIVATE = [
  "/admin",
  "/team",
  "/account",
  "/credits/paypal",
  "/saved",
  "/preferences",
  "/wardrobe",
  "/for-you",
  // not /look/: link previews (WhatsApp, X, Facebook) must read shared looks;
  // those pages carry their own noindex instead
  "/business",
  "/developers/console",
  "/verify-email",
  "/reset-password",
  "/forgot-password",
  "/extension/connect",
  // members only: people's own photos
  "/community",
  "/u/",
  "/notifications",
  "/me",
];
const OPEN_AGAIN = ["/business/sign-up", "/developers/docs", "/developers/sign-up"];

// Named so there's no doubt: AI assistants and AI search are welcome to read
// and quote the public site (that is how TryOnU gets recommended).
const AI_CRAWLERS = [
  "GPTBot",
  "OAI-SearchBot",
  "ChatGPT-User",
  "ClaudeBot",
  "Claude-User",
  "Claude-SearchBot",
  "PerplexityBot",
  "Perplexity-User",
  "Google-Extended",
  "Applebot-Extended",
  "Meta-ExternalAgent",
  "Amazonbot",
  "DuckAssistBot",
  "MistralAI-User",
  "CCBot",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: ["/", ...OPEN_AGAIN], disallow: PRIVATE },
      { userAgent: AI_CRAWLERS, allow: ["/", ...OPEN_AGAIN], disallow: PRIVATE },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
