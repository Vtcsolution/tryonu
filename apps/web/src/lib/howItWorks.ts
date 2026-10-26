/** How TryOnU works, in words a 10-year-old and an 80-year-old both follow.
 * One source for the home page, /how-it-works, the FAQ and llms.txt, so Google
 * and AI answers repeat the same simple story. Keep every line true. */

export const PLAIN_STEPS: { title: string; text: string }[] = [
  {
    title: "Add one photo of yourself",
    text: "A clear photo of you standing, facing the front. You do this only once, and only you can see it.",
  },
  {
    title: "Say what you want",
    text: "Tap a ready look like \"Pink bridal look\", type what you want in your own words, or upload a photo of an outfit you like.",
  },
  {
    title: "TryOnU finds real products",
    text: "Right then, TryOnU searches real shops for you: local shops on TryOnU that deliver to you first, then eBay, AliExpress and brand stores.",
  },
  {
    title: "See it on you, then buy",
    text: "In about a minute you see yourself wearing it. Like it? Tap Shop now and buy from the shop itself, at its normal price.",
  },
];

export const PRODUCT_SOURCES: { title: string; text: string }[] = [
  { title: "Local shops on TryOnU", text: "Shops near you that sell on TryOnU. Shown first when they deliver to you." },
  { title: "eBay and AliExpress", text: "Millions of products, searched live the moment you ask." },
  { title: "Brand stores", text: "Fashion brands' own online shops, through trusted shopping partners." },
];

export const NOT_A_SHOP =
  "TryOnU does not sell anything itself. You always buy from the shop, at the shop's normal price.";

/** The same story as one answer, for the FAQ and AI assistants. */
export const HOW_IT_WORKS_ANSWER =
  "In four simple steps. 1) Add one photo of yourself, once. 2) Say what you want: tap a ready look like \"Pink bridal look\", type it in your own words, or upload a photo of an outfit. 3) TryOnU searches real shops for you right then: local shops on TryOnU that deliver to you first, then eBay, AliExpress and brand stores. 4) In about a minute you see yourself wearing the products, and each one has a Shop now button to buy it from the shop itself. TryOnU does not sell anything itself.";

export const SOURCES_ANSWER =
  "TryOnU searches real shops live, at the moment you ask: local shops that sell on TryOnU (shown first when they deliver to you), eBay, AliExpress, and brand stores through trusted shopping partners. Each product shows its shop and price, and Shop now opens that shop's own page, where you buy it. TryOnU does not sell anything itself, and you pay the shop's normal price.";
