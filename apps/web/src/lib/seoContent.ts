/**
 * The words search engines and AI assistants learn about TryOnU from: the FAQ
 * (/faq, the home page and llms.txt) and the topic pages (/virtual-try-on …).
 * Every answer starts with the direct answer in one or two sentences, then the
 * detail, which is how answer engines quote a page. Keep every claim true:
 * only stores and features that work today.
 */

export type QA = { q: string; a: string };

export const FAQ_GROUPS: { title: string; items: QA[] }[] = [
  {
    title: "Trying on clothes",
    items: [
      {
        q: "What is TryOnU?",
        a: "TryOnU (tryonu.app) is an AI virtual try-on and fashion shopping website. You upload a photo of yourself once, try real clothes, shoes and accessories from real online stores on your own photo, and then buy each piece from the original store.",
      },
      {
        q: "How can I see clothes on myself before buying online?",
        a: "Use a virtual try-on site such as TryOnU: upload one clear photo of yourself standing, pick a product (or describe an outfit to the AI Stylist), and in about 20 to 60 seconds you see a picture of yourself wearing it. Each product links to the store that sells it.",
      },
      {
        q: "Can I try on a whole outfit at once?",
        a: "Yes. TryOnU puts up to five pieces on your photo in one look, for example trousers, a shirt, shoes, sunglasses and a watch. You can then add more pieces to the same look.",
      },
      {
        q: "What can I try on?",
        a: "Clothes (dresses, shirts, trousers, jackets, eastern wear such as shalwar kameez and bridal lehengas), shoes, bags, sunglasses and glasses, watches and jewellery.",
      },
      {
        q: "What photo should I upload?",
        a: "One clear, well-lit photo of you standing and facing the camera, ideally full body, with no filters. A back or side photo is optional and helps with some outfits. You upload it once and reuse it for every try-on.",
      },
      {
        q: "How accurate is a virtual try-on?",
        a: "The picture is made with AI and is a strong preview of how a product looks on you, but fit, size and colour can differ in real life. Always check the store's size chart before you buy.",
      },
    ],
  },
  {
    title: "Shopping",
    items: [
      {
        q: "Where can I buy an outfit after trying it on?",
        a: "On TryOnU every product in your look has a Shop now button that opens the original store's product page, such as eBay, AliExpress, a brand's own shop or a local shop on TryOnU, where you buy it directly. TryOnU never sells the product itself, and you pay the store's normal price.",
      },
      {
        q: "Which stores does TryOnU show products from?",
        a: "eBay, AliExpress, many brand stores through affiliate networks, and local shops that sell on TryOnU. Local shops that deliver to your country are shown first.",
      },
      {
        q: "Can an AI pick an outfit for me?",
        a: "Yes. Describe what you want to the TryOnU AI Stylist, for example \"a navy chino, white shirt and brown loafers for an office in Lahore\", and it picks real products that match and puts them on your photo.",
      },
      {
        q: "Can I try on clothes from eBay, AliExpress or other shops?",
        a: "Yes. Install the free TryOnU browser extension: on any product page, on eBay, AliExpress or any shop, click the TryOnU button (or right-click the product picture) and the product goes onto your own photo, using your TryOnU credits.",
      },
      {
        q: "Can I share my try-on look with friends?",
        a: "Yes. Press Share on a finished look to send a link on WhatsApp, Facebook, LinkedIn, X or email. Your friends see the picture and the products, and can try the same look on themselves.",
      },
    ],
  },
  {
    title: "Credits and price",
    items: [
      {
        q: "How much does TryOnU cost?",
        a: "Try-ons use credits. You buy a credit pack once, with no subscription, by PayPal or card; the current packs and how many looks each gives are on tryonu.app/pricing. If a try-on fails, its credits come back automatically.",
      },
      {
        q: "Can I get free credits?",
        a: "Yes. Share your invite link or any look you made: when a friend joins from it and does their first try-on, you get free credits, and you get more when a shop you invited buys a store plan.",
      },
      {
        q: "Is my photo safe?",
        a: "Your photos are used only to make your try-ons. TryOnU does not sell them or use them to train its own AI, nothing is shared unless you choose to share it, and you can delete your photos at any time.",
      },
    ],
  },
  {
    title: "Shops and developers",
    items: [
      {
        q: "How can my clothing shop sell on TryOnU?",
        a: "Open a store at tryonu.app/sell, choose a plan and add your products (one by one or with a CSV file). Your products are recommended first to shoppers in the areas you deliver to, and shoppers can try them on before they buy.",
      },
      {
        q: "Can I add virtual try-on to my own online store?",
        a: "Yes. TryOnU offers a try-on API, a one-line website widget that adds a \"Try it on\" button to any site, a WordPress/WooCommerce plugin and a Shopify setup. You pay per try-on with prepaid credits, and a failed try-on is free.",
      },
    ],
  },
];

export const ALL_FAQ: QA[] = FAQ_GROUPS.flatMap((g) => g.items);

/** The few questions shown on the home page. */
export const HOME_FAQ: QA[] = [
  ALL_FAQ.find((x) => x.q.startsWith("How can I see clothes"))!,
  ALL_FAQ.find((x) => x.q.startsWith("Where can I buy"))!,
  ALL_FAQ.find((x) => x.q.startsWith("Can I try on a whole outfit"))!,
  ALL_FAQ.find((x) => x.q.startsWith("How much does"))!,
  ALL_FAQ.find((x) => x.q.startsWith("Is my photo safe"))!,
  ALL_FAQ.find((x) => x.q.startsWith("Can I add virtual try-on"))!,
];

// ------------------------------------------------------------------ topic pages

export type Landing = {
  slug: string;
  audience: "shopper" | "business";
  /** <title>, under ~60 characters */
  title: string;
  /** meta description, under ~155 characters */
  description: string;
  kicker: string;
  h1: string;
  /** the direct answer, quoted by search and AI answers */
  answer: string;
  benefits: { title: string; text: string }[];
  steps: { title: string; text: string }[];
  faqs: QA[];
  cta: { label: string; href: string };
  keywords: string[];
  related: string[];
};

const SHOPPER_STEPS = [
  { title: "Add your photo", text: "One clear photo of you, standing and facing the camera. You do this once." },
  { title: "Pick or describe", text: "Choose a product, or tell the AI Stylist what you want in your own words." },
  { title: "See it on you, then buy", text: "In under a minute you see yourself wearing it. Shop now opens the original store." },
];

const WHERE_TO_BUY = ALL_FAQ.find((x) => x.q.startsWith("Where can I buy"))!;
const PHOTO_SAFE = ALL_FAQ.find((x) => x.q.startsWith("Is my photo safe"))!;
const PRICE = ALL_FAQ.find((x) => x.q.startsWith("How much does"))!;
const ACCURACY = ALL_FAQ.find((x) => x.q.startsWith("How accurate"))!;

export const LANDINGS: Landing[] = [
  {
    slug: "virtual-try-on",
    audience: "shopper",
    title: "Virtual Try-On for Clothes Online: See It on You",
    description:
      "Try real clothes, shoes and accessories on your own photo with AI before you buy. Upload one photo, pick a product, see yourself wearing it, then shop the original store.",
    kicker: "Virtual try-on",
    h1: "Virtual try-on for clothes: see any outfit on your own photo",
    answer:
      "TryOnU is a virtual try-on website: upload one photo of yourself, choose real clothes, shoes or accessories from online stores, and AI shows you wearing them in under a minute. Then buy each piece from the original store.",
    benefits: [
      { title: "Your body, not a model's", text: "See how a product looks on you, with your own face, skin tone and shape." },
      { title: "Real products, real stores", text: "Every piece comes from a real store with a real price, and links straight to it." },
      { title: "Whole outfits", text: "Put up to five pieces on in one look: top, bottom, shoes, bag and accessories." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("How can I see clothes"))!, ACCURACY, WHERE_TO_BUY, PHOTO_SAFE],
    cta: { label: "Try it on now", href: "/try" },
    keywords: ["virtual try on clothes", "try on clothes online", "virtual try-on website", "AI try on clothes"],
    related: ["ai-outfit-try-on", "virtual-fitting-room", "ai-personal-stylist"],
  },
  {
    slug: "ai-outfit-try-on",
    audience: "shopper",
    title: "AI Outfit Try-On: Put a Whole Outfit on Your Photo",
    description:
      "Try a complete outfit on yourself with AI: trousers, shirt, shoes, glasses and a watch together in one picture. Real products, each with a link to buy.",
    kicker: "AI outfit try-on",
    h1: "AI outfit try-on: a complete look on you in one picture",
    answer:
      "With TryOnU you can put a whole outfit on your own photo at once: up to five real products such as trousers, a shirt, shoes, sunglasses and a watch. You see the complete look in one picture, and every piece links to the store that sells it.",
    benefits: [
      { title: "See how pieces go together", text: "Colours and styles that look good separately don't always match. See the whole look first." },
      { title: "Describe it in your words", text: "Type \"white shirt, navy chinos, brown loafers\" and the AI Stylist finds real products." },
      { title: "Keep building", text: "Add more pieces to the same look, swap one item, save it and share it." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Can I try on a whole outfit"))!, ALL_FAQ.find((x) => x.q.startsWith("Can an AI pick"))!, WHERE_TO_BUY, PRICE],
    cta: { label: "Build an outfit", href: "/try" },
    keywords: ["AI outfit generator from photo", "outfit try on", "try outfit on my photo", "AI outfit maker"],
    related: ["virtual-try-on", "ai-personal-stylist", "try-on-glasses-watches-jewellery"],
  },
  {
    slug: "virtual-fitting-room",
    audience: "shopper",
    title: "Online Virtual Fitting Room: Try Before You Buy",
    description:
      "A virtual fitting room you can use from your phone: try clothes from real online stores on your own photo, compare looks, and buy the one you like.",
    kicker: "Virtual fitting room",
    h1: "A virtual fitting room on your phone",
    answer:
      "TryOnU works like a fitting room for online shopping: instead of guessing from a model photo, you see the product on your own photo, compare several options side by side, and buy only what you like, from the original store.",
    benefits: [
      { title: "Fewer wrong orders", text: "Decide before you pay, and avoid the hassle of returns." },
      { title: "Compare options", text: "Try several colours or styles and keep the looks you like in your Saved looks." },
      { title: "Works anywhere", text: "On any phone or computer, any time. No app to install." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ACCURACY, ALL_FAQ.find((x) => x.q.startsWith("What photo"))!, WHERE_TO_BUY, PHOTO_SAFE],
    cta: { label: "Open the fitting room", href: "/try" },
    keywords: ["virtual fitting room", "online fitting room", "try before you buy online", "virtual dressing room"],
    related: ["virtual-try-on", "ai-outfit-try-on", "bridal-dress-virtual-try-on"],
  },
  {
    slug: "ai-personal-stylist",
    audience: "shopper",
    title: "AI Personal Stylist That Finds Real Products",
    description:
      "Tell the AI stylist what you need, for an occasion, a budget or a style, and get real products you can try on your own photo and buy from the original store.",
    kicker: "AI stylist",
    h1: "An AI personal stylist that picks real products for you",
    answer:
      "TryOnU's AI Stylist turns a simple request, such as \"an outfit for a summer wedding\", into real products from real stores, then puts them on your photo so you can see the look before you buy.",
    benefits: [
      { title: "Plain words", text: "Describe the occasion, colours or budget. No fashion vocabulary needed." },
      { title: "Your country first", text: "Shops that deliver to you are shown first, including local shops on TryOnU." },
      { title: "From idea to picture", text: "The suggested pieces go straight onto your photo as one look." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Can an AI pick"))!, ALL_FAQ.find((x) => x.q.startsWith("Which stores"))!, WHERE_TO_BUY, PRICE],
    cta: { label: "Ask the AI Stylist", href: "/stylist" },
    keywords: ["AI stylist", "AI personal stylist", "AI fashion assistant", "what should I wear AI"],
    related: ["ai-outfit-try-on", "virtual-try-on", "eastern-wear-virtual-try-on"],
  },
  {
    slug: "bridal-dress-virtual-try-on",
    audience: "shopper",
    title: "Bridal Dress & Lehenga Virtual Try-On",
    description:
      "See a bridal lehenga, wedding dress, jewellery and accessories on your own photo before you buy. Try the complete bridal look with AI, then shop the original store.",
    kicker: "Bridal try-on",
    h1: "Try on a bridal lehenga and wedding look on your own photo",
    answer:
      "With TryOnU a bride can see a complete wedding look on her own photo before buying: the lehenga or dress, dupatta, jewellery, shoes and clutch together in one picture, with a link to buy each piece.",
    benefits: [
      { title: "The whole bridal look", text: "Dress, jewellery and accessories together, so you see how they work as one." },
      { title: "Compare before you commit", text: "Try different colours and styles from different shops and keep the ones you love." },
      { title: "Share with family", text: "Send the look to family on WhatsApp; they can see it and the products in it." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("What can I try on"))!, ALL_FAQ.find((x) => x.q.startsWith("Can I share"))!, WHERE_TO_BUY, ACCURACY],
    cta: { label: "Try a bridal look", href: "/try" },
    keywords: ["bridal lehenga virtual try on", "wedding dress virtual try on", "try bridal dress online", "Pakistani bridal dress try on"],
    related: ["eastern-wear-virtual-try-on", "try-on-glasses-watches-jewellery", "ai-outfit-try-on"],
  },
  {
    slug: "eastern-wear-virtual-try-on",
    audience: "shopper",
    title: "Shalwar Kameez & Eastern Wear Virtual Try-On",
    description:
      "Try shalwar kameez, kurta, lehenga and other eastern wear on your own photo with AI. Local shops first, then buy from the original store.",
    kicker: "Eastern wear",
    h1: "Virtual try-on for shalwar kameez, kurta and eastern wear",
    answer:
      "TryOnU lets you try eastern wear such as shalwar kameez, kurtas, lawn suits and lehengas on your own photo. Local shops that deliver to your country are shown first, and each piece links to the shop that sells it.",
    benefits: [
      { title: "Local shops first", text: "Shops that sell on TryOnU and deliver to you appear before international marketplaces." },
      { title: "Complete the look", text: "Add shoes, a bag or jewellery to the same picture." },
      { title: "For every occasion", text: "Eid, weddings, office or everyday: describe the occasion to the AI Stylist." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Which stores"))!, ALL_FAQ.find((x) => x.q.startsWith("Can an AI pick"))!, WHERE_TO_BUY, PRICE],
    cta: { label: "Try eastern wear", href: "/try" },
    keywords: ["shalwar kameez virtual try on", "kurta try on online", "eastern wear try on", "lawn suit try on"],
    related: ["bridal-dress-virtual-try-on", "ai-personal-stylist", "virtual-try-on"],
  },
  {
    slug: "try-on-glasses-watches-jewellery",
    audience: "shopper",
    title: "Try On Sunglasses, Watches & Jewellery Online",
    description:
      "See sunglasses, glasses, watches, bags and jewellery on your own photo with AI, alone or with a full outfit, then buy from the original store.",
    kicker: "Accessories",
    h1: "Try on sunglasses, watches and jewellery on your own photo",
    answer:
      "TryOnU puts accessories on your photo too: sunglasses and glasses, watches, bags and jewellery, on their own or together with clothes and shoes in one look. Each piece links to the store that sells it.",
    benefits: [
      { title: "Small details matter", text: "See if a watch or a pair of glasses suits your face and style." },
      { title: "With your outfit", text: "Add accessories to a look you already made, one round at a time." },
      { title: "Real listings", text: "Every accessory is a real product with a real price." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("What can I try on"))!, ACCURACY, WHERE_TO_BUY, PHOTO_SAFE],
    cta: { label: "Try accessories", href: "/try" },
    keywords: ["try on sunglasses online", "virtual watch try on", "try on jewellery online", "glasses virtual try on"],
    related: ["ai-outfit-try-on", "virtual-try-on", "bridal-dress-virtual-try-on"],
  },
  {
    slug: "virtual-try-on-for-shopify",
    audience: "business",
    title: "Virtual Try-On for Shopify Stores",
    description:
      "Add a \"Try it on\" button to your Shopify product pages in minutes: no app code. Shoppers see your product on their own photo before they buy. Pay per try-on.",
    kicker: "For Shopify",
    h1: "Add virtual try-on to your Shopify store",
    answer:
      "TryOnU adds a \"Try it on\" button to Shopify product pages with a Custom Liquid block: paste two lines in the theme editor, and shoppers can see your product on their own photo. You pay only for the try-ons used, with prepaid credits.",
    benefits: [
      { title: "No app to build", text: "Online Store → Themes → Customize → Add block → Custom Liquid → paste. Done." },
      { title: "Uses your product photos", text: "Each product's own main image is used automatically." },
      { title: "Safe by design", text: "Your website key only works on your own domain; a failed try-on is free." },
    ],
    steps: [
      { title: "Create a developer account", text: "Sign up at tryonu.app/developers and buy a credit pack." },
      { title: "Create a website key", text: "Enter your shop's domain; the key only works there." },
      { title: "Paste the block", text: "Add a Custom Liquid block to your product page and save." },
    ],
    faqs: [
      ALL_FAQ.find((x) => x.q.startsWith("Can I add virtual try-on"))!,
      { q: "Does it work with any Shopify theme?", a: "Yes. The button is added with a Custom Liquid block, which every Online Store 2.0 theme supports, and it uses each product's own main photo." },
      { q: "How is it priced?", a: "With prepaid credits: one credit is one try-on, credits never expire, and a failed try-on gives the credit back. See tryonu.app/developers for the packs." },
    ],
    cta: { label: "Get your website key", href: "/developers/sign-up" },
    keywords: ["Shopify virtual try on", "virtual try on app Shopify", "Shopify try on button", "AI try on for Shopify"],
    related: ["virtual-try-on-for-woocommerce", "virtual-try-on-api"],
  },
  {
    slug: "virtual-try-on-for-woocommerce",
    audience: "business",
    title: "Virtual Try-On Plugin for WordPress & WooCommerce",
    description:
      "Install the TryOnU plugin, paste your website key, and a \"Try it on\" button appears on every WooCommerce product. Shoppers see your products on their own photo.",
    kicker: "For WooCommerce",
    h1: "Virtual try-on plugin for WordPress and WooCommerce",
    answer:
      "The TryOnU plugin adds a \"Try it on\" button under Add to cart on every WooCommerce product: install it, paste your website key in Settings, and shoppers can see your product on their own photo before buying. You pay per try-on with prepaid credits.",
    benefits: [
      { title: "Install and go", text: "Plugins → Add New → Upload → Activate, then paste your key. No coding." },
      { title: "Every product, automatically", text: "The button uses each product's main image, or place it anywhere with [tryonu_button]." },
      { title: "Your colours", text: "Choose the button text and colour to match your shop." },
    ],
    steps: [
      { title: "Create a developer account", text: "Sign up at tryonu.app/developers and buy a credit pack." },
      { title: "Install the plugin", text: "Download it from the API docs and upload it in WordPress." },
      { title: "Paste your website key", text: "Settings → TryOnU Try-On. The button appears on your products." },
    ],
    faqs: [
      ALL_FAQ.find((x) => x.q.startsWith("Can I add virtual try-on"))!,
      { q: "Where does the button appear?", a: "Under the Add to cart button on every product with a main image, or wherever you place the [tryonu_button] shortcode." },
      { q: "Is my customers' data safe?", a: "The shopper's photo is used only to make the try-on picture shown to them. Your website key only works on your own domain." },
    ],
    cta: { label: "Get the plugin", href: "/developers/docs" },
    keywords: ["WooCommerce virtual try on plugin", "WordPress virtual try on", "virtual fitting room plugin", "try on button WooCommerce"],
    related: ["virtual-try-on-for-shopify", "virtual-try-on-api"],
  },
  {
    slug: "virtual-try-on-api",
    audience: "business",
    title: "Virtual Try-On API for Fashion Apps & Stores",
    description:
      "A simple REST API for AI virtual try-on: send a person photo and a product photo, get back a picture of the person wearing it. Prepaid credits, failed try-ons free.",
    kicker: "Try-on API",
    h1: "Virtual try-on API: add AI try-on to your app or website",
    answer:
      "The TryOnU API takes a photo of a person and a photo of a product and returns a picture of that person wearing it, usually in 20 to 60 seconds. It is a simple REST API with code for cURL, JavaScript, Python, PHP and WordPress, paid with prepaid credits.",
    benefits: [
      { title: "Two photos in, one picture out", text: "POST the photos as files or links, then read the result when it's ready." },
      { title: "Website widget too", text: "No backend? A one-line widget adds a Try it on button to any site." },
      { title: "Fair pricing", text: "One credit per try-on, credits never expire, failed try-ons are free." },
    ],
    steps: [
      { title: "Create a developer account", text: "Sign up at tryonu.app/developers." },
      { title: "Create a secret key", text: "Keep it on your server; buy a credit pack." },
      { title: "Call the API", text: "Copy the code for your language from the docs." },
    ],
    faqs: [
      ALL_FAQ.find((x) => x.q.startsWith("Can I add virtual try-on"))!,
      { q: "How fast is a try-on?", a: "Usually 20 to 60 seconds. You start a try-on, then ask for its result until it is completed." },
      { q: "What does a try-on cost?", a: "One prepaid credit. Credits never expire, and a failed try-on gives the credit back. See tryonu.app/developers for the packs." },
    ],
    cta: { label: "Read the API docs", href: "/developers/docs" },
    keywords: ["virtual try on API", "AI try on API", "clothing try on API", "fashion try on API"],
    related: ["virtual-try-on-for-shopify", "virtual-try-on-for-woocommerce"],
  },
];

export const LANDINGS_BY_SLUG: Record<string, Landing> = Object.fromEntries(LANDINGS.map((l) => [l.slug, l]));
