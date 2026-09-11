/**
 * Marketing photography — free images from Unsplash (Unsplash License:
 * free for commercial use, no permission needed). These are placeholders
 * for real product / model imagery; swap the `src` values when the
 * product-ingestion pipeline and try-on renders come online.
 *
 * Host is allowlisted in next.config.ts (`images.remotePatterns`).
 * All are used with <Image fill> inside an aspect-ratio box.
 */

const U = (id: string) =>
  `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=1200&q=80`;

export type Photo = { src: string; alt: string };

export const PHOTOS = {
  portraitStudio: {
    src: U("1524504388940-b1c1722653e1"),
    alt: "Studio portrait of a person, neutral background",
  },
  portraitWinter: {
    src: U("1487412720507-e7ab37603c6f"),
    alt: "Portrait of a smiling person outdoors in a scarf and beanie",
  },
  lookPinkCoat: {
    src: U("1485462537746-965f33f7f6a7"),
    alt: "Full-length look: a person in a pink wrap coat on a city street",
  },
  lookBlueCoat: {
    src: U("1539109136881-3be0616acf4b"),
    alt: "Editorial full-length look: a person in a sky-blue coat in a European plaza",
  },
  lookYellowSet: {
    src: U("1515886657613-9f3515b0c78f"),
    alt: "Full-length look: a person in a yellow tracksuit outdoors",
  },
  shoppingBags: {
    src: U("1483985988355-763728e1935b"),
    alt: "A person holding shopping bags against a bright wall",
  },
  clothingRail: {
    src: U("1490481651871-ab68de25d43d"),
    alt: "A rail of neutral-toned garments on wooden hangers",
  },
  productSweater: {
    src: U("1434389677669-e08b4cac3105"),
    alt: "A cream knit poncho sweater on a wooden hanger",
  },
  productDress: {
    src: U("1595777457583-95e059d581b8"),
    alt: "A person in a flowing red evening dress outdoors",
  },
  productJacket: {
    src: U("1591047139829-d91aecb6caea"),
    alt: "A rust-coloured bomber jacket held up on a hanger",
  },
} satisfies Record<string, Photo>;
