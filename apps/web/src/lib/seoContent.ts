/**
 * The words search engines and AI assistants learn about TryOnU from: the FAQ
 * (/faq, the home page and llms.txt) and the topic pages (/virtual-try-on …).
 * Every answer starts with the direct answer in one or two sentences, then the
 * detail, which is how answer engines quote a page. Keep every claim true:
 * only stores and features that work today.
 */
import { HOW_IT_WORKS_ANSWER, SOURCES_ANSWER } from "@/lib/howItWorks";

export type QA = { q: string; a: string };

export const FAQ_GROUPS: { title: string; items: QA[] }[] = [
  {
    title: "Trying on clothes",
    items: [
      {
        q: "How does TryOnU work?",
        a: HOW_IT_WORKS_ANSWER,
      },
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
        a: "Yes. TryOnU puts a whole outfit on your photo in one look, for example a bridal lehenga, dupatta, jewellery, khussa and clutch, or trousers, a shirt, shoes and a watch. Type a ready look like \"Pink bridal look\" and TryOnU finds every piece. You can then add more pieces to the same look.",
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
        q: "Where do the products on TryOnU come from?",
        a: SOURCES_ANSWER,
      },
      {
        q: "Can an AI pick an outfit for me?",
        a: "Yes. Tap a ready look such as \"Pink bridal look\", \"Eid outfit\" or \"Office look\", or describe what you want in your own words, and the AI Stylist picks real products that match and puts them on your photo.",
      },
      {
        q: "Can I try on clothes from eBay, AliExpress or other shops?",
        a: "Yes. Install the free TryOnU browser extension: on any product page, on eBay, AliExpress or any shop, click the TryOnU button (or right-click the product picture) and the product goes onto your own photo, using your TryOnU credits.",
      },
      {
        q: "Can I try on several products from one shop together?",
        a: "Yes. On a shop's own TryOnU website, press Try it on on each product you like, then press Try on at the bottom. TryOnU opens with all of them already chosen: add your photo and see them on you together in one picture, then order from the shop.",
      },
      {
        q: "Does TryOnU work in the USA, UK, Canada, Australia and Japan?",
        a: "Yes. TryOnU works in any country, in the browser on a phone or computer, with nothing to install. Products come from stores that ship internationally, such as eBay, AliExpress and brand stores, and each product shows its store, price and delivery. The website also shows itself in the visitor's language by country, for example Japanese in Japan.",
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
        q: "Can my shop get its own website on TryOnU?",
        a: "Yes. Every store on TryOnU gets its own website at tryonu.app/your-store-name with its logo, products, product pages, a cart and checkout. Shoppers try products on their own photo before ordering, orders are sent to the shop by email, and the shop's WhatsApp button is on every page. Plans are on tryonu.app/sell.",
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
  ALL_FAQ.find((x) => x.q.startsWith("How does TryOnU work"))!,
  ALL_FAQ.find((x) => x.q.startsWith("Where do the products"))!,
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
  /** longer sections after the steps, each with its own H2 */
  sections?: { h2: string; paragraphs: string[] }[];
  /** real ready looks shown on the page */
  looks?: { season?: string; audience?: "women" | "men" | "kids"; limit: number };
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
      "Try real clothes, shoes and accessories on your own photo with AI before you buy. One photo, pick a product, see it on you, then shop the store.",
    kicker: "Virtual try-on",
    h1: "Virtual try-on for clothes: see any outfit on your own photo",
    answer:
      "TryOnU is a virtual try-on website: upload one photo of yourself, choose real clothes, shoes or accessories from online stores, and AI shows you wearing them in under a minute. Then buy each piece from the original store.",
    benefits: [
      { title: "Your body, not a model's", text: "See how a product looks on you, with your own face, skin tone and shape." },
      { title: "Real products, real stores", text: "Every piece comes from a real store with a real price, and links straight to it." },
      { title: "Whole outfits", text: "Put a whole outfit on in one look: clothes, shoes, bag and jewellery." },
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
      "With TryOnU you can put a whole outfit on your own photo at once: real products such as trousers, a shirt, shoes, sunglasses and a watch. You see the complete look in one picture, and every piece links to the store that sells it.",
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
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Can an AI pick"))!, ALL_FAQ.find((x) => x.q.startsWith("Where do the products"))!, WHERE_TO_BUY, PRICE],
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
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Where do the products"))!, ALL_FAQ.find((x) => x.q.startsWith("Can an AI pick"))!, WHERE_TO_BUY, PRICE],
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
      "Add a \"Try it on\" button to your Shopify product pages in minutes, no app code. Shoppers see your product on their own photo. Pay per try-on.",
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
      "Install the TryOnU plugin, paste your website key, and every WooCommerce product gets a \"Try it on\" button. Shoppers see it on their own photo.",
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
  {
    slug: "ai-clothes-changer",
    audience: "shopper",
    title: "AI Clothes Changer: Change Clothes on Your Photo",
    description:
      "Change the clothes in your own photo with AI, using real products from real shops. See the new outfit on you, then buy each piece from the shop.",
    kicker: "AI clothes changer",
    h1: "Change the clothes on your photo with AI, using real products",
    answer:
      "TryOnU is an AI clothes changer that uses real products: add one photo of yourself, pick clothes, shoes or jewellery from real shops (or type a look like \"Eid outfit\"), and in about a minute you see yourself wearing them. Unlike photo filters, every piece is a real product you can buy.",
    benefits: [
      { title: "Real clothes, not filters", text: "Every item is a real product from a real shop, with its price and a Shop now button." },
      { title: "Your own face and body", text: "The AI keeps your face, body and background and changes only the clothes." },
      { title: "One piece or a whole outfit", text: "Change just the shirt, or the whole look: clothes, shoes, bag and jewellery." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("How does TryOnU work"))!, ACCURACY, PHOTO_SAFE, PRICE],
    cta: { label: "Change my clothes", href: "/try" },
    keywords: ["AI clothes changer", "change clothes in photo", "outfit changer AI", "change clothes AI", "AI dress changer"],
    related: ["virtual-try-on", "ai-outfit-try-on", "virtual-try-on-app"],
  },
  {
    slug: "virtual-try-on-app",
    audience: "shopper",
    title: "Virtual Try-On App for Clothes on Your Phone",
    description:
      "Try clothes on your own photo from your phone. TryOnU works in any phone browser and can be added to your home screen like an app, no download needed.",
    kicker: "Try-on app",
    h1: "A virtual try-on app that works on any phone",
    answer:
      "TryOnU works on any phone, Android or iPhone, straight from the browser at tryonu.app, and you can add it to your home screen so it opens like an app. Add one photo of yourself, pick real products from real shops, and see them on you in about a minute.",
    benefits: [
      { title: "No app store needed", text: "Open tryonu.app and tap Add to Home Screen. It opens like an app, with no download." },
      { title: "Works on every phone", text: "Android, iPhone and tablets, and on computers too, with the same account." },
      { title: "Your looks everywhere", text: "Looks you save on your phone are on your computer too." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("How does TryOnU work"))!, ALL_FAQ.find((x) => x.q.startsWith("What photo"))!, PRICE, PHOTO_SAFE],
    cta: { label: "Open TryOnU", href: "/try" },
    keywords: ["virtual try on app", "try on clothes app", "AI try on app", "virtual fitting app", "try on clothes online app"],
    related: ["virtual-try-on", "ai-clothes-changer", "virtual-fitting-room"],
  },
  {
    slug: "eid-outfit-try-on",
    audience: "shopper",
    title: "Eid Outfit Try-On: See Your Eid Dress on You",
    description:
      "See your Eid dress, shalwar kameez, kurta and jewellery on your own photo before you buy. Type \"Eid outfit\" and TryOnU finds every piece in real shops.",
    kicker: "Eid outfits",
    h1: "See your Eid outfit on you before you buy",
    answer:
      "Type \"Eid outfit\" on TryOnU and it finds a complete look in real shops (shalwar kameez, dupatta, jewellery and shoes for women, or shalwar kameez, waistcoat and chappals for men) and shows it on your own photo in about a minute. Then buy each piece from the shop.",
    benefits: [
      { title: "The whole Eid look", text: "Clothes, dupatta, jewellery and shoes together, so you see the full outfit." },
      { title: "For women and men", text: "Shalwar kameez and kurta for men and women, with matching accessories." },
      { title: "Share with family", text: "Send the look on WhatsApp and decide together before you buy." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Can I try on a whole outfit"))!, ALL_FAQ.find((x) => x.q.startsWith("Where do the products"))!, WHERE_TO_BUY, PRICE],
    cta: { label: "Try an Eid outfit", href: "/try" },
    keywords: ["Eid outfit", "Eid dress", "Eid outfit ideas", "Eid shalwar kameez", "Eid kurta for men", "Eid dress try on"],
    related: ["eastern-wear-virtual-try-on", "bridal-dress-virtual-try-on", "groom-sherwani-virtual-try-on"],
  },
  {
    slug: "groom-sherwani-virtual-try-on",
    audience: "shopper",
    title: "Groom Sherwani Virtual Try-On: See It on You",
    description:
      "See a sherwani, khussa, shawl and watch on your own photo before your wedding. Type \"Groom look\" and TryOnU finds every piece in real shops.",
    kicker: "Groom try-on",
    h1: "Try on a groom sherwani and wedding look on your own photo",
    answer:
      "Type \"Groom look\" on TryOnU and it finds a sherwani, khussa, shawl and watch in real shops and shows them on your own photo in about a minute. Compare colours and styles, then buy each piece from the shop.",
    benefits: [
      { title: "The full groom look", text: "Sherwani, khussa, shawl and watch together in one picture." },
      { title: "Compare colours", text: "Ivory, gold, maroon or black: see which suits you before you buy." },
      { title: "Decide with family", text: "Share the look on WhatsApp so everyone can see it." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Can I try on a whole outfit"))!, ALL_FAQ.find((x) => x.q.startsWith("Can I share"))!, WHERE_TO_BUY, ACCURACY],
    cta: { label: "Try a groom look", href: "/try" },
    keywords: ["sherwani try on", "groom sherwani", "groom outfit", "barat dress for groom", "wedding sherwani for men"],
    related: ["bridal-dress-virtual-try-on", "eid-outfit-try-on", "eastern-wear-virtual-try-on"],
  },
  {
    slug: "virtual-try-on-pakistan",
    audience: "shopper",
    title: "Virtual Try-On in Pakistan: Try Clothes Online",
    description:
      "Try clothes, lehengas, shalwar kameez and jewellery on your own photo before you buy online in Pakistan. Local shops that deliver to you are shown first.",
    kicker: "Pakistan",
    h1: "Try clothes on your photo before you buy online in Pakistan",
    answer:
      "TryOnU lets shoppers in Pakistan see clothes on their own photo before buying online. Local shops on TryOnU that deliver to you are shown first, then eBay, AliExpress and brand stores. You see the product on you in about a minute, then buy from the shop itself.",
    benefits: [
      { title: "Local shops first", text: "Shops on TryOnU that deliver in your city are shown before shops abroad." },
      { title: "Eastern and western wear", text: "Lehenga, shalwar kameez, kurta, abaya, jeans, shoes and jewellery." },
      { title: "Pay by card or PayPal", text: "Buy credit packs by card or PayPal. A failed try-on gives its credits back." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Where do the products"))!, ALL_FAQ.find((x) => x.q.startsWith("How can my clothing shop"))!, PRICE, PHOTO_SAFE],
    cta: { label: "Start trying on", href: "/try" },
    keywords: ["virtual try on Pakistan", "try clothes online Pakistan", "online shopping Pakistan", "Pakistani dresses online", "AI try on Pakistan"],
    related: ["eastern-wear-virtual-try-on", "bridal-dress-virtual-try-on", "eid-outfit-try-on"],
  },
  {
    slug: "try-on-clothes-before-buying",
    audience: "shopper",
    title: "Try On Clothes Before Buying Online: See Them on You",
    description:
      "See how clothes look on you before you buy online. Upload one photo, pick real products from real stores, and AI shows you wearing them in about a minute.",
    kicker: "Before you buy",
    h1: "How to see clothes on yourself before buying online",
    answer:
      "To see clothes on yourself before buying online, use a virtual try-on site such as TryOnU: upload one clear photo of you standing, pick a product from a real store, and AI shows you wearing it in about a minute. If you like it, buy it from the store itself.",
    benefits: [
      { title: "Fewer wrong buys", text: "See the colour and style on your own photo first, not only on a model." },
      { title: "Any store", text: "Products from eBay, AliExpress and brand stores, plus any shop page with the free browser extension." },
      { title: "Whole outfits too", text: "Put a top, trousers, shoes and a bag on you together and see if they go." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("How can I see clothes"))!, ACCURACY, ALL_FAQ.find((x) => x.q.startsWith("What photo should"))!, PRICE],
    cta: { label: "Try something on", href: "/try" },
    keywords: ["try on clothes before buying online", "see clothes on me before buying", "how will this look on me", "try clothes on virtually", "virtual try on clothes free"],
    related: ["virtual-try-on", "ai-outfit-try-on", "virtual-fitting-room"],
  },
  {
    slug: "wedding-guest-outfit-try-on",
    audience: "shopper",
    title: "Wedding Guest Outfit Try-On: See the Look on You",
    description:
      "Not sure what to wear to a wedding? Try wedding guest dresses, suits, shoes and accessories on your own photo with AI, then buy from the store.",
    kicker: "Wedding guest",
    h1: "Wedding guest outfits: try the whole look on you first",
    answer:
      "TryOnU lets you try a wedding guest outfit on your own photo before you buy: a dress or suit, shoes, a bag and jewellery together in one picture. Type something like \"summer wedding guest dress, sage green\" or \"navy suit for a wedding\" and the AI Stylist finds real products to try.",
    benefits: [
      { title: "The full look at once", text: "Dress or suit, shoes, bag and jewellery together, so you know they match." },
      { title: "Describe the wedding", text: "Garden, beach, evening or black tie: say it in your words and get real products." },
      { title: "Buy from the store", text: "Every piece links to the store that sells it, at its normal price." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Can I try on a whole outfit"))!, ALL_FAQ.find((x) => x.q.startsWith("Can an AI pick"))!, WHERE_TO_BUY, ACCURACY],
    cta: { label: "Try a wedding guest look", href: "/try" },
    keywords: ["wedding guest outfit", "wedding guest dresses", "what to wear to a wedding", "wedding guest outfit men", "wedding guest outfit ideas"],
    related: ["ai-outfit-try-on", "ai-personal-stylist", "try-on-glasses-watches-jewellery"],
  },
  {
    slug: "winter-outfit-try-on",
    audience: "shopper",
    title: "Winter Outfit Ideas to Try On Your Own Photo",
    description:
      "Complete winter outfits for women, men and kids from real stores: coats, jackets, knitwear and boots. See each look on your own photo before you buy.",
    kicker: "Winter outfits",
    h1: "Winter outfit ideas you can try on yourself",
    answer:
      "TryOnU has ready winter looks for women, men and kids, each put together from real products: coats, puffer jackets, sweaters, jeans and boots. Pick a look and see it on your own photo in about a minute, or describe your own winter outfit to the AI Stylist.",
    benefits: [
      { title: "Ready looks", text: "Complete winter outfits for women, men and kids, ready to try on." },
      { title: "Layers that work", text: "See a coat over a sweater with jeans and boots together, not one piece at a time." },
      { title: "Shop every piece", text: "Each item links to its store, with its real price." },
    ],
    steps: SHOPPER_STEPS,
    faqs: [ALL_FAQ.find((x) => x.q.startsWith("Can I try on a whole outfit"))!, ALL_FAQ.find((x) => x.q.startsWith("Can an AI pick"))!, WHERE_TO_BUY, PRICE],
    cta: { label: "See the winter looks", href: "/looks/winter" },
    keywords: ["winter outfit ideas", "winter outfits for women", "winter outfits for men", "kids winter outfits", "winter coat outfit", "what to wear in winter"],
    related: ["ai-outfit-try-on", "virtual-try-on", "ai-personal-stylist"],
    looks: { season: "Winter", limit: 9 },
    sections: [
      {
        h2: "Winter outfits for UK weather: rain, wind and the office",
        paragraphs: [
          "A British winter is more wet than freezing, usually somewhere between 2 and 10°C, so the outfit has to handle rain and wind as well as cold. Start with a coat that covers your hips: a wool overcoat for the office, or a water-resistant parka or quilted jacket for the school run and weekends.",
          "Underneath, a fine-knit jumper or a roll neck keeps you warm on the train without overheating once you are inside. Dark jeans or wool trousers, and leather Chelsea boots or chunky trainers with a good grip, finish the look. Add a scarf in a colour from the coat and the whole outfit holds together.",
        ],
      },
      {
        h2: "Winter outfits for snow and real cold in the US and Canada",
        paragraphs: [
          "Where winter means snow and temperatures below -10°C, warmth comes first. A long puffer or a down parka with a hood, a thermal base layer, a thick sweater and insulated, waterproof boots with a deep tread do most of the work. Gloves and a beanie are not optional.",
          "For the office or an evening out, a wool coat over a turtleneck with straight-leg trousers looks sharp, and you can keep snow boots in your bag for the walk. Try the coat and boots together on your photo: a long puffer changes your proportions, and seeing it on you first saves a return.",
        ],
      },
      {
        h2: "Travelling from the UAE to a cold country this winter",
        paragraphs: [
          "Flying from Dubai or Abu Dhabi to London, Paris, Toronto or New York in December or January means packing a wardrobe you rarely need at home. Pack light: one versatile coat in camel, navy or black, two or three knitted layers, one pair of warm, comfortable boots and a scarf that works with everything.",
          "For modest winter dressing, long wool coats, knitted maxi dresses and wide-leg trousers layer well and stay warm. Try the full outfit on your photo before you travel, so you only buy the pieces you will actually wear on the trip.",
        ],
      },
      {
        h2: "How to check a winter outfit before you buy",
        paragraphs: [
          "Winter clothes are expensive and bulky to send back, so check three things first: the coat length against your height, the colour of the coat next to your face, and whether the boots suit the trousers. A virtual try-on shows all three on your own photo in about a minute. Then check the shop's size chart, delivery time to your country and returns policy, and buy from the shop itself.",
        ],
      },
    ],
  },
  {
    slug: "virtual-try-on-for-fashion-brands",
    audience: "business",
    title: "Virtual Try-On for Fashion Brands and Retailers",
    description:
      "Let shoppers see your clothes on their own photo before they buy. Add a Try it on button to your site, use the API, or sell from your own TryOnU store.",
    kicker: "For brands",
    h1: "Virtual try-on for fashion brands and online retailers",
    answer:
      "TryOnU gives fashion brands and retailers AI virtual try-on: shoppers see your product on their own photo before they buy. Add a Try it on button to your website (Shopify, WooCommerce or any site), call the try-on API, or sell from your own store website on TryOnU. You pay per try-on with prepaid credits, and a failed try-on is free.",
    benefits: [
      { title: "On your own site", text: "A one-line widget, a Shopify block or the WordPress/WooCommerce plugin adds Try it on to your product pages." },
      { title: "Or your own TryOnU store", text: "A store website at tryonu.app/your-brand with try-on, cart, orders by email and a WhatsApp button." },
      { title: "See what shoppers try", text: "Your store dashboard shows the try-on pictures customers made with your products." },
    ],
    steps: [
      { title: "Pick how to start", text: "A website key for your own site, or a store on TryOnU." },
      { title: "Add your products", text: "Your product photos are used as they are; for a TryOnU store, add products or upload a CSV file." },
      { title: "Shoppers try, then buy", text: "They see your product on their own photo and buy from you." },
    ],
    faqs: [
      ALL_FAQ.find((x) => x.q.startsWith("Can I add virtual try-on"))!,
      ALL_FAQ.find((x) => x.q.startsWith("Can my shop get its own website"))!,
      { q: "How is it priced?", a: "Website and API try-ons use prepaid credit packs (one credit is one try-on, a failed try-on gives it back); see tryonu.app/developers. A store on TryOnU has a monthly plan; see tryonu.app/sell." },
    ],
    cta: { label: "Get started", href: "/developers" },
    keywords: ["virtual try on for fashion brands", "virtual try on for retailers", "virtual fitting room software", "AI try on for ecommerce", "virtual try on solution"],
    related: ["virtual-try-on-for-shopify", "virtual-try-on-for-woocommerce", "virtual-try-on-api"],
  },
];

export const LANDINGS_BY_SLUG: Record<string, Landing> = Object.fromEntries(LANDINGS.map((l) => [l.slug, l]));
