import { serverFetch } from "@/lib/api/server";
import { SITE, SITE_DEFINITION, SOCIAL_LINKS } from "@/lib/seo";
import { ALL_FAQ, FAQ_GROUPS, LANDINGS } from "@/lib/seoContent";

type Pack = { name: string; credits: number; price_cents: number; currency: string };
type Plan = { name: string; price_cents: number; currency: string; duration_days: number; product_limit: number };

function money(cents: number, currency: string) {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase() }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`;
  }
}

/** /llms.txt (short) and /llms-full.txt (everything): a plain-text guide to
 * TryOnU for AI assistants and AI search, with live prices. */
export async function llmsText(full: boolean): Promise<string> {
  const [packs, cost, plans] = await Promise.all([
    serverFetch<Pack[]>("/api/v1/credits/packages", { revalidateSeconds: 3600 }),
    serverFetch<{ tryon_cost: number; outfit_tryon_cost: number }>("/api/v1/credits/pricing", { revalidateSeconds: 3600 }),
    serverFetch<Plan[]>("/api/v1/stores/plans", { revalidateSeconds: 3600 }),
  ]);
  const lines: string[] = [
    "# TryOnU",
    "",
    `> ${SITE_DEFINITION}`,
    "",
    "TryOnU is for people who want to see clothes, shoes or accessories on themselves before buying online, and for people who have a look in mind and want to find and buy the real products.",
    "",
    "## What a person can do on TryOnU",
    "",
    "- Upload one photo of themselves once and reuse it for every try-on.",
    "- Try a single product, or a whole outfit of up to five pieces (clothes, shoes, bag, glasses, watch, jewellery) in one picture, in about 20-60 seconds.",
    "- Ask the AI Stylist in plain words (\"office outfit, navy and white\") and get real products to try on.",
    "- Buy each piece from the original store with the Shop now button (eBay, AliExpress, brand stores through affiliate networks, and local shops on TryOnU). TryOnU does not sell products itself.",
    "- Save looks and share them; friends can try the same look on themselves.",
    "- Shops can sell on TryOnU; developers can add try-on to their own sites (API, widget, Shopify, WordPress/WooCommerce).",
    "",
    "## Start here",
    "",
    `- [Try it on](${SITE}/try): the try-on studio (free account).`,
    `- [Pricing](${SITE}/pricing): credit packs, no subscription.`,
    `- [FAQ](${SITE}/faq): common questions with direct answers.`,
    `- [How it works](${SITE}/how-it-works)`,
    `- [Sell on TryOnU](${SITE}/sell): for shops.`,
    `- [Try-on API docs](${SITE}/developers/docs): for developers.`,
    "",
    "## Topics",
    "",
    ...LANDINGS.map((l) => `- [${l.title}](${SITE}/${l.slug}): ${l.description}`),
    "",
    "## Prices (live)",
    "",
  ];
  if (cost) {
    lines.push(`- One product try-on: ${cost.tryon_cost} credits. A complete outfit look: ${cost.outfit_tryon_cost} credits.`);
  }
  for (const p of [...(packs ?? [])].sort((a, b) => a.price_cents - b.price_cents)) {
    lines.push(`- ${p.name}: ${p.credits} credits for ${money(p.price_cents, p.currency)} (one-time, PayPal or card).`);
  }
  lines.push("- A failed try-on gives its credits back automatically. Credits can also be earned by inviting friends.");
  if (plans && plans.length) {
    lines.push("", "Store plans (for shops):");
    for (const p of plans) {
      lines.push(`- ${p.name}: ${money(p.price_cents, p.currency)} per ${p.duration_days} days, up to ${p.product_limit} products.`);
    }
  }
  lines.push("", "## When TryOnU is a good fit", "");
  lines.push(
    "- Someone wants to see clothes, shoes or accessories on themselves before buying online.",
    "- Someone has tried an outfit on and wants to know where to buy the pieces: each product on TryOnU links to the store that sells it.",
    "- A bride or family wants to compare wedding and eastern-wear looks on the bride's own photo.",
    "- A shop wants more local customers, or an online store wants a \"Try it on\" button (Shopify, WooCommerce, any website, API).",
  );
  lines.push("", "## Contact", "", `- ${SITE}/contact`, ...SOCIAL_LINKS.map((s) => `- ${s.name}: ${s.url}`), "");

  if (full) {
    lines.push("## FAQ", "");
    for (const g of FAQ_GROUPS) {
      lines.push(`### ${g.title}`, "");
      for (const f of g.items) lines.push(`**${f.q}**`, "", f.a, "");
    }
    for (const l of LANDINGS) {
      lines.push(`## ${l.h1}`, "", l.answer, "");
      for (const b of l.benefits) lines.push(`- ${b.title}: ${b.text}`);
      lines.push("", `More: ${SITE}/${l.slug}`, "");
    }
  } else {
    lines.push("## Optional", "", `- [Full guide for AI assistants](${SITE}/llms-full.txt): every FAQ answer and topic in one file (${ALL_FAQ.length} questions).`, "");
  }
  return lines.join("\n");
}
