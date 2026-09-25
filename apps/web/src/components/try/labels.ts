/** A caption for one item, in the words a shopper would use.
 *
 * Retailers title a listing to be found, not to be read: "Prada PR17WS
 * 1AB5S049 Women's Sunglasses" truncates to "Prada PR17WS 1AB5S049
 * Women's..." in a 150px card, which names everything except the item.
 * The full title stays on the card's tooltip and in the list below. */

// Listed most specific first, so "maang tikka" wins over "tikka" and
// "clutch" over "bag". Words that are ambiguous on their own ("top",
// "chain") come last, after everything that would otherwise be misread
// as one. A word already plural is matched as written; anything else
// matches with or without its "s", because retailers title the same
// thing both ways ("Ava Dress Sandal", "Strappy Sandals").
const NOUNS = [
  "maang tikka", "salwar kameez", "shalwar kameez", "lehenga choli", "nose pin",
  "dupatta", "lehenga", "kameez", "sherwani", "kurti", "kurta", "saree", "sari", "abaya",
  "khussa", "peshawari", "jutti", "stiletto", "sandal", "sneaker", "loafer", "pump",
  "heels", "flats", "boot", "shoe",
  "sunglasses", "eyeglasses", "spectacles", "goggles", "glasses",
  "jhumka", "chandbali", "earring", "stud", "tikka", "nath",
  "necklace", "choker", "pendant", "bracelet", "bangle", "kada", "anklet", "payal",
  "cufflink", "ring", "watch",
  "clutch", "handbag", "backpack", "tote", "purse", "bag",
  "scarf", "stole", "shawl", "hijab", "turban", "beanie", "cap", "hat",
  "blazer", "jacket", "trench coat", "coat", "cardigan", "hoodie", "sweater", "waistcoat",
  "t-shirt", "shirt", "blouse", "gown", "dress", "skirt",
  "palazzo", "trousers", "jeans", "chinos", "shorts", "leggings", "pants", "chain", "top",
];

// Things that come in twos are named in twos, the way a shopper says
// them: a card reading "Shoe" beside a photo of two shoes is a typo the
// reader has to forgive.
const PAIRED: Record<string, string> = {
  shoe: "shoes", sandal: "sandals", sneaker: "sneakers", boot: "boots",
  loafer: "loafers", pump: "pumps", stiletto: "stilettos",
  earring: "earrings", stud: "stud earrings", jhumka: "jhumka earrings",
  chandbali: "chandbali earrings", bangle: "bangles", cufflink: "cufflinks",
};

export function shortLabel(name: string, slot?: string | null): string {
  const lower = name.toLowerCase();
  const found = NOUNS.find((noun) => {
    const word = noun.endsWith("s") ? noun : `${noun}s?`;
    return new RegExp(`(^|[^a-z])${word}([^a-z]|$)`).test(lower);
  });
  if (found) return titled(PAIRED[found] ?? found);
  if (slot && slot !== "other") return titled(slot.replace(/_/g, " "));
  return name.split(/\s+/).slice(0, 3).join(" ");
}

function titled(words: string): string {
  return words.replace(/(^|\s|-)\w/g, (c) => c.toUpperCase());
}
