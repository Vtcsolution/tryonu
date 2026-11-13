import { formatPrice } from "@/components/try/shop";
import type { ReadyLook } from "@/lib/api/endpoints";
import { serverFetch } from "@/lib/api/server";
import { lookPath, lookSlug } from "@/lib/lookSlug";

export { lookPath, lookSlug };

/** Ready looks for search: readable addresses (/looks/womens-winter-look-white-coat-1a2b3c4d),
 * the collections (/looks/women …) and the words each look page says about itself. */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function publishedLooks(): Promise<ReadyLook[]> {
  return (await serverFetch<ReadyLook[]>("/api/v1/looks?limit=96", { revalidateSeconds: 300 })) ?? [];
}

export type LookCollection = {
  slug: string;
  audience?: ReadyLook["audience"];
  season?: string;
  /** <title>, under 60 characters with " | TryOnU" */
  title: string;
  description: string;
  h1: string;
  intro: string[];
};

/** Indexable only with this many looks in them; fewer reads as a thin page. */
export const MIN_COLLECTION = 6;

export const LOOK_COLLECTIONS: LookCollection[] = [
  {
    slug: "women",
    audience: "women",
    title: "Women's Outfits to Try On Before You Buy",
    description:
      "Complete women's outfits from real shops: coats, knitwear, dresses, boots and bags. See each look on your own photo with AI, then shop every piece.",
    h1: "Women's outfits you can try on yourself",
    intro: [
      "Every look here is a complete women's outfit put together from products you can buy today: a coat or jacket, knitwear or a dress, trousers or jeans, shoes, and often a bag or jewellery. Each piece comes from a real shop with a real price.",
      "Press a look to see every piece and its shop. Press Try this look on you, add one photo, and in about a minute you see the whole outfit on yourself, so you can judge the colours and the shape on you, not on a model.",
    ],
  },
  {
    slug: "men",
    audience: "men",
    title: "Men's Outfits to Try On Before You Buy",
    description:
      "Complete men's outfits from real shops: overcoats, jackets, knitwear, trousers, trainers and boots. See each look on your own photo, then shop each piece.",
    h1: "Men's outfits you can try on yourself",
    intro: [
      "Each look is a complete men's outfit made from products in real shops: an overcoat, puffer or jacket, a jumper or shirt, trousers or jeans, and trainers or boots. Every piece links to the shop that sells it.",
      "Not sure a camel coat or a chunky knit suits you? Press Try this look on you, add one photo, and see the whole outfit on yourself in about a minute before you spend anything on clothes.",
    ],
  },
  {
    slug: "winter",
    season: "Winter",
    title: "Winter Looks: Shop Complete Outfits",
    description:
      "Shop complete winter outfits for women and men: wool coats, puffers, knitwear and boots from real shops. Try each look on your own photo before you buy.",
    h1: "Winter looks to shop and try on",
    intro: [
      "These are complete winter outfits, ready to shop: warm coats and puffer jackets, knitwear, trousers and jeans, and boots or trainers that work in cold, wet weather. Each look lists every piece with its shop and price.",
      "Layers are hard to judge one product at a time. Try the whole look on your own photo first: you see how the coat length, the colours and the boots work together on you, then buy only what you like.",
    ],
  },
];

export function collectionLooks(c: LookCollection, looks: ReadyLook[]): ReadyLook[] {
  return looks.filter((l) => (!c.audience || l.audience === c.audience) && (!c.season || l.season === c.season));
}

export type ResolvedLook =
  | { kind: "look"; look: ReadyLook; published: boolean }
  | { kind: "redirect"; to: string }
  | { kind: "collection"; collection: LookCollection; looks: ReadyLook[] };

/** What /looks/<param> is: a look by its readable address, an old id address
 * (redirected to the readable one), or a collection page. */
export async function resolveLookParam(param: string): Promise<ResolvedLook | null> {
  const looks = await publishedLooks();
  const collection = LOOK_COLLECTIONS.find((c) => c.slug === param);
  if (collection) {
    const inIt = collectionLooks(collection, looks);
    return inIt.length >= MIN_COLLECTION ? { kind: "collection", collection, looks: inIt } : null;
  }
  if (UUID.test(param)) {
    const listed = looks.find((l) => l.id === param);
    if (listed) return { kind: "redirect", to: lookPath(listed) };
    // not published (a team preview): shown at its id address, kept out of search
    const look = await serverFetch<ReadyLook>(`/api/v1/looks/${encodeURIComponent(param)}`, { revalidateSeconds: 120 });
    return look ? { kind: "look", look, published: false } : null;
  }
  const exact = looks.find((l) => lookSlug(l) === param);
  if (exact) return { kind: "look", look: exact, published: true };
  // the title changed since the link was made: the id part still finds it
  const idPart = /-([0-9a-f]{8})$/.exec(param)?.[1];
  const renamed = idPart ? looks.find((l) => l.id.startsWith(idPart)) : undefined;
  return renamed ? { kind: "redirect", to: lookPath(renamed) } : null;
}

const AUDIENCE: Record<ReadyLook["audience"], string> = { women: "women's", men: "men's", kids: "kids'" };

/** A product name from a marketplace, cut to what a person would say ("Women's Wool Coat"). */
export function shortName(name: string): string {
  const head = name.split(/\s[|–-]\s|,|\(/)[0].trim();
  const words = head.split(/\s+/);
  return words.slice(0, 7).join(" ");
}

function listing(parts: string[]): string {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

export function lookShops(look: ReadyLook): string[] {
  return [...new Set(look.items.map((i) => i.shop).filter((s): s is string => !!s))];
}

export function lookTotal(look: ReadyLook): string | null {
  return look.total_cents != null && look.currency ? formatPrice(look.total_cents, look.currency) : null;
}

/** <title> under 60 characters where the look's own title allows it. */
export function lookTitle(look: ReadyLook): string {
  const full = `${look.title} | TryOnU`;
  return full.length <= 60 ? full : look.title;
}

export function lookDescription(look: ReadyLook): string {
  const shops = lookShops(look);
  const total = lookTotal(look);
  const from = shops.length ? ` from ${listing(shops.slice(0, 2))}${shops.length > 2 ? " and more" : ""}` : "";
  const n = look.items.length;
  const text = `${look.title}: ${n} ${n === 1 ? "piece" : "pieces"}${from}${total ? `, ${total} in total` : ""}. See the whole outfit on your own photo before you buy.`;
  return text.length <= 155 ? text : `${text.slice(0, 152).replace(/\s+\S*$/, "")}…`;
}

/** The paragraphs a look page says about the look (occasion, how to wear it,
 * where the pieces come from, the price). Built from the look's own data. */
export function lookCopy(look: ReadyLook): { styling: string[]; buying: string[] } {
  const who = AUDIENCE[look.audience];
  const season = look.season?.toLowerCase() ?? "";
  const pieces = look.items.map((i) => shortName(i.name));
  const shops = lookShops(look);
  const total = lookTotal(look);

  const one = look.items.length === 1;
  const styling = [
    one
      ? `This ${who} ${season ? `${season} ` : ""}look is built around one piece: ${pieces[0]}.`
      : `This ${who} ${season ? `${season} ` : ""}outfit puts ${look.items.length} pieces together: ${listing(pieces)}.`,
  ];
  if (season === "winter") {
    styling.push(
      "It is built in layers, so it works for a cold commute and a heated office alike. In the UK, swap in a waterproof or keep a compact umbrella for the rain; in snowy parts of the US and Canada, add a thermal base layer and check the boots have a grippy sole. Keep the colours close to the look and every piece still goes with the rest of your wardrobe.",
    );
  } else if (season === "wedding") {
    styling.push(
      "It is made for a wedding or a dressy evening. Check the invitation for a dress code, keep the jewellery to the pieces shown so the outfit stays balanced, and pick shoes you can stand and dance in for a few hours.",
    );
  } else {
    styling.push(
      one
        ? "Wear it with shoes and a bag you already own in a matching or neutral colour, and let this piece be the one that stands out."
        : "Wear it as shown, or keep the main piece and swap one item for something you already own; the colours are chosen to go together, so one change keeps the look working.",
    );
  }

  const buying = [
    `${shops.length ? `${one ? "It comes" : "The pieces come"} from ${listing(shops)}. ` : ""}${one ? "The Shop button opens" : "Each Shop button opens"} the store's own product page, where you check sizes, delivery to your country and returns before you buy.${total ? ` ${one ? "It costs" : "Bought together, the look costs"} about ${total} at today's prices; shops can change their prices.` : ""}`,
    `Not sure it suits you? Press Try this look on you: add one clear photo and see ${one ? "it" : "the whole outfit"} on yourself in about a minute, then decide ${one ? "whether to buy it" : "which pieces to buy"}.`,
  ];
  return { styling, buying };
}
