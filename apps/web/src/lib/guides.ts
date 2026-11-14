/**
 * /guides: articles for searches a landing page can't answer on its own.
 * Written for UK readers first (British spelling), each linking to its
 * landing page and showing real looks. Keep every claim true: Amazon
 * products are not in TryOnU search yet.
 */
import type { QA } from "@/lib/seoContent";

export type Guide = {
  slug: string;
  audience: "shopper" | "business";
  /** <title>, under ~50 characters (" | TryOnU" is added) */
  title: string;
  description: string;
  h1: string;
  published: string;
  updated: string;
  /** the direct answer, first */
  answer: string;
  sections: { h2: string; paragraphs: string[] }[];
  faqs: QA[];
  /** the landing page this guide supports */
  landing: { slug: string; label: string };
  looks?: { season?: string; audience?: "women" | "men" | "kids"; limit: number };
  keywords: string[];
};

export const GUIDES: Guide[] = [
  {
    slug: "amazon-try-before-you-buy-alternative",
    audience: "shopper",
    title: "Amazon Try Before You Buy Alternative",
    description:
      "Amazon ended Prime Try Before You Buy in January 2025. Here is how to check clothes on yourself before you order, and what still works for returns.",
    h1: "An alternative to Amazon's Try Before You Buy",
    published: "2026-11-13",
    updated: "2026-11-13",
    answer:
      "Amazon's Prime Try Before You Buy ended on 31 January 2025, so you can no longer order clothes to try at home and pay only for what you keep. The closest alternative is to try the clothes on your own photo first with a virtual try-on site such as TryOnU, then order one size you are confident about from a shop with free or easy returns.",
    sections: [
      {
        h2: "What happened to Prime Try Before You Buy",
        paragraphs: [
          "Prime Try Before You Buy (first called Prime Wardrobe) let Prime members order up to six eligible clothing, shoe and accessory items, try them at home for seven days, and pay only for the ones they kept. Amazon stopped taking new orders through it on 31 January 2025.",
          "Amazon said at the time that many clothing items still come with free returns, and pointed shoppers to size recommendations, review highlights and virtual try-on instead. In practice that means you pay up front and send back what doesn't work, which is exactly the hassle the old programme removed.",
        ],
      },
      {
        h2: "What to do instead: see it on you, then order once",
        paragraphs: [
          "The reason people ordered three sizes or three colours was uncertainty: will it suit me, and will it fit? You can answer the first question before you spend anything. Upload one clear photo of yourself to TryOnU, pick a product, and in about a minute you see yourself wearing it. If the colour washes you out or the coat length looks wrong on you, you have saved an order and a return.",
          "For fit, use the shop's size chart with your own measurements (chest, waist, hips and inside leg), and read reviews for comments such as 'runs small'. Then order one size. If you are between sizes, pick the shop whose returns are free.",
        ],
      },
      {
        h2: "Can I try on Amazon clothes on TryOnU?",
        paragraphs: [
          "Not directly yet. Amazon products are not in TryOnU's search today: the connection is built and waiting for Amazon's approval, so it is coming soon. TryOnU's search shows products from eBay, AliExpress, brand stores, and shops that sell on TryOnU.",
          "Today you can still try a product photo from any shop on yourself. In the try-on studio, press the + button and choose Upload your own item, then add a clear photo of the product on a plain background. TryOnU puts it on your photo like any other item. It is your private try-on: nothing is posted anywhere.",
        ],
      },
      {
        h2: "Your rights when you return clothes in the UK",
        paragraphs: [
          "For most things you buy online in the UK, the Consumer Contracts Regulations give you 14 days after delivery to cancel, then another 14 days to send the item back, and the shop must refund you within 14 days of getting it back. Who pays for the return postage depends on the shop's policy, and more fashion shops now charge for it, which is one more reason to check the look on yourself before you order.",
        ],
      },
    ],
    faqs: [
      {
        q: "Does Amazon still have Try Before You Buy?",
        a: "No. Amazon ended Prime Try Before You Buy on 31 January 2025. Many clothing items on Amazon still have free returns, but you pay first and return what you don't keep.",
      },
      {
        q: "Is there a free alternative to Try Before You Buy?",
        a: "Yes. A new TryOnU member's first complete outfit is free: the credits arrive once you confirm your email, one free outfit per person. Joining and the AI Stylist are free too, and some products from shops selling on TryOnU can be tried on for free, paid by the shop.",
      },
      {
        q: "Can I try on a product from any website?",
        a: "Yes. In the try-on studio, press + and Upload your own item, then add a clear photo of the product. TryOnU puts it on your own photo.",
      },
    ],
    landing: { slug: "try-on-clothes-before-buying", label: "Try on clothes before buying online" },
    looks: { season: "Winter", limit: 3 },
    keywords: ["amazon try before you buy alternative", "prime try before you buy ended", "try clothes before buying amazon"],
  },
  {
    slug: "try-on-ebay-clothes",
    audience: "shopper",
    title: "How to Try On eBay Clothes Before You Buy",
    description:
      "eBay clothes come in every size system and condition. See an eBay item on your own photo first, then check the seller's returns and measurements.",
    h1: "How to try on eBay clothes before you buy",
    published: "2026-11-13",
    updated: "2026-11-13",
    answer:
      "To try on eBay clothes before you buy, search for the item in TryOnU's try-on studio (eBay listings are part of its live search), press Try this on, and see it on your own photo in about a minute. If you like it, the Shop button opens the eBay listing, where you check the seller's returns and the measurements before you buy.",
    sections: [
      {
        h2: "Why eBay clothes are harder to judge",
        paragraphs: [
          "eBay is brilliant for brands at lower prices, pre-loved designer pieces and things the high street sold out of. It is also harder to judge than a shop's own website: photos are taken by each seller, sizes can be UK, EU, US or Asian, and returns are set seller by seller, with some listings saying no returns at all.",
          "So the two questions are the same as anywhere (will it suit me, will it fit?), but getting them wrong costs more, because a return may not be possible.",
        ],
      },
      {
        h2: "Method 1: search eBay inside TryOnU",
        paragraphs: [
          "Open the try-on studio, add your photo once, and type what you want in the search box, for example 'Barbour waxed jacket' or 'black wool coat women'. Results come live from eBay and other shops, each with its shop name and price. Press Try this on and the item goes onto your photo.",
          "Want a whole outfit? Describe it to the AI Stylist ('navy overcoat, grey jumper, dark jeans, brown boots') and it finds real products, eBay listings included, and puts them on you together in one picture.",
        ],
      },
      {
        h2: "Method 2: try the listing photo itself",
        paragraphs: [
          "Found a listing elsewhere, or a one-off pre-loved piece that search doesn't show? Save a clear photo of the item from the listing, ideally on a plain background, then in the studio press + and Upload your own item. TryOnU puts that exact piece on your photo.",
        ],
      },
      {
        h2: "Check these before you press Buy it now",
        paragraphs: [
          "Measurements beat size labels. Good sellers give armpit-to-armpit, length and waist in centimetres or inches; compare them with a similar item you own. For pre-loved items, read the condition notes and zoom into the photos for marks or pilling.",
          "Read the returns section of the listing. eBay's Money Back Guarantee covers items that don't arrive or aren't as described, not a change of mind, so if the seller doesn't accept returns, seeing the item on yourself first matters even more.",
        ],
      },
    ],
    faqs: [
      {
        q: "Can I try on eBay clothes virtually?",
        a: "Yes. eBay listings are part of TryOnU's live product search: press Try this on and the item appears on your own photo. You can also upload a listing's photo with Upload your own item.",
      },
      {
        q: "Does trying on with TryOnU change the eBay price?",
        a: "No. The Shop button opens the eBay listing and you pay the seller's normal price. Some shops pay TryOnU a small commission on sales, at no cost to you.",
      },
    ],
    landing: { slug: "virtual-try-on", label: "Virtual try-on for clothes" },
    looks: { season: "Winter", audience: "men", limit: 3 },
    keywords: ["how to try on ebay clothes", "try on ebay clothes virtually", "ebay clothes sizing"],
  },
  {
    slug: "try-on-aliexpress-clothes",
    audience: "shopper",
    title: "Try On AliExpress Clothes Before Ordering",
    description:
      "AliExpress clothes are cheap but slow and hard to return. See the item on your own photo first, check centimetre sizes and photo reviews, then order.",
    h1: "How to try on AliExpress clothes before you order",
    published: "2026-11-13",
    updated: "2026-11-13",
    answer:
      "To try on AliExpress clothes before ordering, search for the item in TryOnU's try-on studio (AliExpress products are part of its live search) and press Try this on to see it on your own photo. Then check the size chart in centimetres and the buyers' photos on AliExpress before you order, because returns from overseas are slow.",
    sections: [
      {
        h2: "Why it pays to check AliExpress clothes first",
        paragraphs: [
          "AliExpress has huge choice at low prices, but each order travels from overseas. Delivery to the UK, US, Canada or the UAE often takes one to three weeks, and sending something back can take as long again. A mistake costs you a month, not a day.",
          "The two usual problems are size and colour. Many sellers use Asian sizing, which often runs smaller than UK sizes, and product photos are sometimes edited, so the real colour can be different.",
        ],
      },
      {
        h2: "See it on yourself first",
        paragraphs: [
          "Open the try-on studio, add one clear photo of yourself, and search for what you want, for example 'oversized knit cardigan' or 'satin slip dress'. AliExpress results appear with their shop and price. Press Try this on and you see the piece on you in about a minute, so you can judge the style and colour on your own body and skin tone.",
          "If the item you found isn't in the results, save its main product photo and use + then Upload your own item in the studio to try that exact piece.",
        ],
      },
      {
        h2: "Then check size, photos and delivery",
        paragraphs: [
          "Ignore the S, M, L label and read the size chart in centimetres. Measure a similar item you own flat on a table and compare. If you are between sizes, go up one.",
          "Open the reviews with photos: real buyers' pictures show the true colour and fabric. Check the delivery estimate to your country and whether the listing offers free returns. In the UK, VAT on orders up to £135 is charged at checkout, so the price you see is usually the price you pay.",
        ],
      },
    ],
    faqs: [
      {
        q: "Can I try on AliExpress clothes virtually?",
        a: "Yes. AliExpress products are part of TryOnU's live search: press Try this on and the item appears on your own photo before you order.",
      },
      {
        q: "Do AliExpress clothes run small?",
        a: "Often, yes, because many sellers use Asian sizing. Always compare the centimetre measurements in the size chart with clothes you already own.",
      },
    ],
    landing: { slug: "virtual-try-on", label: "Virtual try-on for clothes" },
    looks: { season: "Winter", audience: "women", limit: 3 },
    keywords: ["try on aliexpress clothes before ordering", "aliexpress clothes sizing", "aliexpress virtual try on"],
  },
  {
    slug: "avoid-clothing-returns-uk",
    audience: "shopper",
    title: "How to Avoid Clothing Returns in the UK",
    description:
      "Six practical steps to stop sending clothes back: measure yourself, convert sizes, read reviews, see the item on your own photo and know your rights.",
    h1: "How to avoid returning clothes you buy online in the UK",
    published: "2026-11-13",
    updated: "2026-11-13",
    answer:
      "To avoid returning clothes you buy online, measure yourself and compare with the garment's measurements, not just the size label; read reviews for fit; and see the item on your own photo with a virtual try-on before you order. Order one size from shops with clear returns, and keep the tags on until you are sure.",
    sections: [
      {
        h2: "Why clothes go back",
        paragraphs: [
          "Most returns come down to two things: it didn't fit, or it looked different on me. The first is a measuring problem, the second is a seeing problem, and both are easier to solve before you order than after.",
          "Returns also cost more than they used to. Many UK fashion shops now charge a fee for returns by post, and every parcel back is time spent printing labels and queuing at a drop-off point.",
        ],
      },
      {
        h2: "1. Measure yourself once, properly",
        paragraphs: [
          "With a soft tape measure, take your chest or bust, natural waist, hips and inside leg, and write them in your phone. Measure over thin clothes, keep the tape level and don't pull it tight. Update the numbers every few months.",
        ],
      },
      {
        h2: "2. Compare measurements, not labels",
        paragraphs: [
          "A UK 10 is roughly an EU 38 and a US 6, but brands differ, and shops abroad may use Asian sizing. Open the size chart and compare your measurements with it. For coats and knitwear, compare with a similar item you own and like the fit of.",
        ],
      },
      {
        h2: "3. Read the reviews for fit",
        paragraphs: [
          "Look for comments such as 'runs small', 'size up' or 'long in the arms', and for reviewers who give their height and usual size. Photo reviews show the real colour.",
        ],
      },
      {
        h2: "4. See it on yourself before you order",
        paragraphs: [
          "A virtual try-on answers the 'will it suit me?' question. On TryOnU you upload one photo, pick a product from a real shop or describe an outfit to the AI Stylist, and in about a minute you see yourself wearing it. If the colour or shape is wrong for you, you've avoided a return before it started.",
        ],
      },
      {
        h2: "5. Know your rights",
        paragraphs: [
          "Under the Consumer Contracts Regulations you normally have 14 days from delivery to cancel an online order, then 14 more days to send it back, and the shop must refund you within 14 days of receiving it. Keep tags on and try things on at home over clean underwear so the item stays returnable.",
        ],
      },
    ],
    faqs: [
      {
        q: "How long do I have to return clothes bought online in the UK?",
        a: "Normally 14 days from delivery to tell the shop you are cancelling, then 14 more days to send the item back. Many shops offer longer; check their returns page.",
      },
      {
        q: "Does virtual try-on help with fit?",
        a: "It shows how a product looks on you (style, colour, length) but not the exact fit. Use it together with the size chart and your own measurements.",
      },
    ],
    landing: { slug: "try-on-clothes-before-buying", label: "Try on clothes before buying online" },
    looks: { season: "Winter", limit: 3 },
    keywords: ["avoid returns buying clothes online uk", "how to avoid clothing returns", "online clothes returns uk"],
  },
  {
    slug: "what-to-wear-in-snow-canada",
    audience: "shopper",
    title: "What to Wear in Snow in Canada: Layering Guide",
    description:
      "How to dress for snow and real cold in Canada: base, mid and outer layers, boots, and what visitors from the UK or UAE should pack. With looks to try on.",
    h1: "What to wear in snow in Canada",
    published: "2026-11-13",
    updated: "2026-11-13",
    answer:
      "For snow in Canada, dress in three layers: a thin base layer that wicks sweat (merino or synthetic, not cotton), a warm middle layer such as fleece or a down vest, and a windproof, waterproof insulated parka with a hood. Add insulated waterproof boots with a deep tread, wool socks, a hat, a scarf or neck warmer and proper gloves or mittens.",
    sections: [
      {
        h2: "The three-layer rule",
        paragraphs: [
          "Cold in much of Canada is drier and harsher than a British winter: days of -10°C to -20°C are common in January, and wind chill makes it feel colder. Layers trap warm air and let you adjust when you walk from the street into a heated shop or office.",
          "Base layer: long-sleeved merino wool or synthetic thermals; cotton holds sweat and makes you cold. Middle layer: a fleece, a thick wool jumper or a light down vest. Outer layer: a knee- or thigh-length parka that is windproof and water-resistant, with a hood that fits over a hat.",
        ],
      },
      {
        h2: "Feet, hands and head",
        paragraphs: [
          "Most people feel the cold first in their feet. Choose insulated, waterproof winter boots with a thick, grippy sole and enough room for wool socks; fashion boots and trainers soak through in slush. Mittens are warmer than gloves on very cold days. A hat that covers your ears and a scarf or neck warmer complete the outfit.",
        ],
      },
      {
        h2: "Looking good in the city",
        paragraphs: [
          "In Toronto, Montreal or Vancouver you don't need to dress like you are on an expedition. A long wool coat or a smart puffer over a roll neck, dark jeans or wool trousers and leather boots with a rubber sole look polished and keep you warm for a commute. Keep a thermal layer underneath on the coldest days.",
          "Because a long parka changes your proportions, try the coat and boots together on your photo before you buy: it is the quickest way to see whether a knee-length or hip-length style suits you.",
        ],
      },
      {
        h2: "Visiting from the UK or the UAE",
        paragraphs: [
          "A British winter coat is often not enough for a Canadian January. If you are visiting, buy or borrow one proper insulated parka and one pair of winter boots, and bring layers from home. From the UAE, pack thermals, a warm jumper or two and gloves, and plan to buy the parka and boots for your size and the city's weather.",
        ],
      },
    ],
    faqs: [
      {
        q: "What should I wear in snow in Canada?",
        a: "Three layers (thermal base, warm middle, windproof insulated parka), insulated waterproof boots, wool socks, a hat, a scarf and mittens or gloves.",
      },
      {
        q: "Is a wool coat warm enough for a Canadian winter?",
        a: "For a city commute on milder days, yes, with a thermal layer underneath. For long walks or very cold days below -15°C, an insulated parka is warmer.",
      },
    ],
    landing: { slug: "winter-outfit-try-on", label: "Winter outfit ideas" },
    looks: { season: "Winter", limit: 6 },
    keywords: ["what to wear in snow canada", "canada winter clothes", "how to dress for canadian winter"],
  },
  {
    slug: "reduce-returns-with-ai-try-on",
    audience: "business",
    title: "Reducing Clothing Returns With AI Try-On",
    description:
      "Why shoppers return clothes, what AI virtual try-on can and can't fix, how to add it to a Shopify, WooCommerce or TryOnU store, and how to measure it.",
    h1: "Reducing clothing returns with AI virtual try-on",
    published: "2026-11-13",
    updated: "2026-11-13",
    answer:
      "AI virtual try-on can reduce returns caused by 'it looked different on me', because shoppers see your product on their own photo before they buy. It does not replace size guidance for fit. Add a Try it on button to your product pages (or sell from a TryOnU store), pair it with clear size charts, and compare return rates and reasons for products with and without try-on.",
    sections: [
      {
        h2: "Why customers send clothes back",
        paragraphs: [
          "Return reasons fall into two groups. Fit: too small, too big, wrong length. Look: the colour, the shape or the style looked different on the customer than on the model. Delivery damage and wrong items are a small share by comparison.",
          "Fit is a measurement problem, solved with good size charts, garment measurements and fit notes from reviews. Look is a visual problem, and that is where try-on helps: the customer sees your product on themselves, with their own skin tone and shape, before they order.",
        ],
      },
      {
        h2: "What AI try-on does, and what it doesn't",
        paragraphs: [
          "TryOnU puts your product photo onto the shopper's own photo in about a minute, either one product or a whole outfit. It shows colour, style, length and how pieces go together. It is an AI picture, not a fitting, so it does not tell the customer their size; keep your size chart next to the button.",
          "Shoppers' photos are sensitive. TryOnU uses them only for the shopper's own try-ons, never sells them, and lets them delete their photos at any time. Mention this near the button so customers feel safe using it.",
        ],
      },
      {
        h2: "Three ways to add it",
        paragraphs: [
          "On your own website: a one-line widget adds a Try it on button to product pages. On Shopify it goes in with a Custom Liquid block (there is no Shopify App Store app yet); on WordPress there is a WooCommerce plugin. You pay per try-on with prepaid credits, and a failed try-on is free.",
          "Through the API: build try-on into your own app or checkout; packs start at $35. Or sell from your own store website on TryOnU, from $15 a month, with try-on, a cart, orders by email and WhatsApp, and a dashboard that shows the try-on pictures customers made with your products.",
        ],
      },
      {
        h2: "How to measure the effect",
        paragraphs: [
          "Start with a few best-selling products that have high returns for 'looked different'. Turn try-on on for them and note, over the same weeks, the conversion rate, the return rate and the return reasons, compared with similar products without it. Ask customers who used try-on whether it helped them decide. Keep the test running long enough to cover a few hundred orders before drawing conclusions.",
        ],
      },
    ],
    faqs: [
      {
        q: "Does virtual try-on reduce returns?",
        a: "It targets returns where the product looked different on the customer than expected. It doesn't solve fit on its own, so pair it with clear size charts and measure the result on your own products.",
      },
      {
        q: "How much does TryOnU cost for a store?",
        a: "Website and API try-ons use prepaid packs from $35, one credit per try-on, failed try-ons free. A store website on TryOnU starts at $15 a month.",
      },
    ],
    landing: { slug: "virtual-try-on-for-fashion-brands", label: "AI virtual try-on for fashion brands" },
    keywords: ["reduce clothing returns with ai", "virtual try on returns", "ai ecommerce tools for clothing stores"],
  },
];

export const GUIDES_BY_SLUG: Record<string, Guide> = Object.fromEntries(GUIDES.map((g) => [g.slug, g]));
