import type { Metadata } from "next";

/**
 * Search and AI-answer basics, in one place.
 *
 * SITE_DEFINITION is the one sentence every search engine and AI assistant
 * should learn about TryOnU: the same words on the home page, in llms.txt,
 * in structured data and on the About page, so answers quote it consistently.
 * Keep every claim here true: assistants repeat what they read.
 */

export const SITE = "https://tryonu.app";
export const SITE_NAME = "TryOnU";

export const SITE_DEFINITION =
  "TryOnU (tryonu.app) is an AI virtual try-on and fashion shopping platform: you upload a photo of yourself once, try real clothes, shoes, bags, watches, glasses and jewellery from real online stores on your own photo, then buy each piece from the original store.";

export const SITE_TAGLINE = "Try it. See you. Shop it.";

/** TryOnU's official social accounts: linked from the footer and named in the
 * site's structured data (sameAs), so search engines and AI assistants know
 * these profiles are the same brand. */
export const SOCIAL_LINKS: { name: "Facebook" | "Instagram" | "TikTok"; url: string; handle: string }[] = [
  { name: "Instagram", url: "https://www.instagram.com/tryonu.app/", handle: "@tryonu.app" },
  { name: "TikTok", url: "https://www.tiktok.com/@tryonuapp", handle: "@tryonuapp" },
  { name: "Facebook", url: "https://www.facebook.com/tryonu", handle: "facebook.com/tryonu" },
];

export const CORE_KEYWORDS = [
  "virtual try-on",
  "virtual try on clothes",
  "AI try on clothes online",
  "try clothes on your photo",
  "AI outfit try-on",
  "virtual fitting room",
  "AI stylist",
  "see clothes on yourself before buying",
  "online shopping try before you buy",
  "TryOnU",
];

/** The usual, complete set of tags for a public page. */
export function pageMeta({
  title,
  description,
  path,
  keywords = [],
  image,
}: {
  title: string;
  description: string;
  path: string;
  keywords?: string[];
  image?: string;
}): Metadata {
  const url = `${SITE}${path === "/" ? "" : path}`;
  const images = image ? [{ url: image }] : undefined;
  // the brand once, at the end, unless the title already names it
  const full = title.includes(SITE_NAME) ? title : `${title} | ${SITE_NAME}`;
  return {
    title: { absolute: full },
    description,
    keywords: [...keywords, ...CORE_KEYWORDS].slice(0, 20),
    alternates: { canonical: path },
    openGraph: { type: "website", url, title: full, description, siteName: SITE_NAME, ...(images ? { images } : {}) },
    twitter: { card: "summary_large_image", title: full, description, ...(image ? { images: [image] } : {}) },
  };
}

/** Pages that belong to one person (account, saved looks, payments): kept out of search results. */
export const PRIVATE_PAGE: Metadata["robots"] = { index: false, follow: false };
