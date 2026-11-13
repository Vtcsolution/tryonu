# TryOnU SEO audit (13 November 2026)

Crawled from the live site (https://tryonu.app, commit 48152a4) by fetching every URL in sitemap.xml (110 URLs) and reading the server-rendered HTML, then checked against the code. Word counts include the header, footer and navigation.

## Verdict on the issues reported before the audit

| Reported | Found in code and HTML | Action in this branch |
|---|---|---|
| /looks/{id}: UUID URLs | True | Readable addresses: `/looks/womens-winter-look-white-coat-and-white-heels-b7311b82`. Old UUID links redirect permanently (308, which Google treats like a 301). If a look is renamed, the old address still redirects (the last 8 characters are the id). |
| /looks/{id}: no meta description | Not true: every look had one, but it was the first four product names glued together ("Pakistani Designer Georgette Anarkali Suit...") | Written per look: title, number of pieces, shops, total price |
| /looks/{id}: no canonical, OG, Twitter, JSON-LD | Not true: self canonical, OG and Twitter with the look picture, ItemList with Product/Offer were all there | Kept. BreadcrumbList added |
| /looks/{id}: about 60 words | Partly: about 350 words with navigation, but only about 40 words about the look itself | About 150 to 200 words per look: how to wear it (UK rain, US and Canada snow for winter looks), where the pieces come from, total price, how to try it on; links to photo policy and privacy; 4 more looks |
| /looks/{id}: titles | 36 of 36 titles were 60 to 82 characters ("... : Try It On You / TryOnU") | "Look title / TryOnU", under 60 where the look's own title allows |
| Prices only show "$" | True for US dollars (en-US formatting) | Prices now read "US$48.75". GBP/CAD/AED conversions not done yet (needs an exchange-rate source; see Next) |
| No hreflang | True, and correct: translation is client-side on the same URL (components/i18n/AutoTranslate.tsx), so Google only sees English | No hreflang added. One English canonical per page |
| /winter-outfit-try-on: no country angle, links only to /looks | True | UK, US/Canada and UAE sections, "how to check a winter outfit", 9 real winter looks linked, about 1,070 words |
| Sign-up pages in the sitemap | True (/sign-up, /business/sign-up, /developers/sign-up) | Removed from the sitemap; `noindex, follow` on all three |
| Test stores in the sitemap | True (zee-store, tryonu-fashion and their products) | **Waiting for your decision** (not changed) |
| Missing looks give soft 404 | Not true: /looks/<unknown> already returned 404 | Still 404 |
| Organization sameAs | Already present (Instagram, TikTok, Facebook, LinkedIn) | Kept |

## Other findings

- **lastmod was always "now"** for every static page, which teaches Google to ignore it. Static pages now have no lastmod; looks use their creation date, stores their last update.
- **Two ready looks have a prompt as their title** ("Winter for coats, sweaters, boots, scarves or wool"). Rename them in the team panel: the title is now the URL, H1 and title tag.
- **/looks and /winter-outfit-try-on both targeted "winter outfits".** /looks is now "Shop the Look: Complete Outfits to Try On"; /looks/winter is "Winter Looks: Shop Complete Outfits"; /winter-outfit-try-on keeps "winter outfit ideas".
- **Collections:** /looks/women (15 looks), /looks/men (21), /looks/winter (31) are now indexable pages. /looks/kids has 0 looks, so it returns 404 and is not linked (a collection needs 6 looks).
- **SoftwareApplication schema:** the home page had a WebApplication with one AggregateOffer. Now the same WebApplication (a SoftwareApplication type) lists each live credit pack as an Offer, on /, /pricing and /virtual-try-on-app. No ratings or reviews: there are none to show honestly.
- **Images:** no `<img>` without alt text on any crawled page. Product and look cards below the fold use `loading="lazy"`; the first three look cards and the look picture load eagerly (likely LCP).
- **API pages in Google:** three api.tryonu.app shop-link redirects were indexed. Fixed on tryon-fixes (ce85dd8): the API sends `X-Robots-Tag: noindex` on everything except images.

## Core Web Vitals risks

- **LCP on look pages:** the look picture comes from api.tryonu.app as a JPEG, not through Next's image optimiser. The small card is about 87 KB; the full card is larger. Serving WebP/AVIF in two or three sizes with `srcset` would cut LCP on phones.
- **Plain `<img>` almost everywhere:** only 6 uses of next/image. Product images from eBay/AliExpress arrive at their original size.
- **JavaScript:** about 2 MB of JS chunks in the whole build (all routes together). The try studio and admin are the heaviest; marketing pages share the common chunks.
- **Fonts:** Inter and Playfair Display through next/font (self-hosted, `display: swap`): low risk.
- **Client-only grids:** the /looks grid is a client component with server-provided first data, so it is in the HTML; filters load on tap. Fine for crawling.

## Every indexable route (live, before this branch)

| Route | Title (chars) | Description (chars) | Canonical | H1 | Schema | Words |
|---|---|---|---|---|---|---|
| / | TryOnU: AI Virtual Try-On. See Clothes on You Before You Buy (60) | 149 | self | Try real fashion on youbefore you buy. | WebApplication, FAQPage | 1668 |
| /looks | Ready Looks: Winter Outfits to Try On You / TryOnU (50) | 149 | self | Ready looks, to try on you | ItemList | 1422 |
| /how-it-works | How Virtual Try-On Works: From Your Photo to Your Cart / TryOnU (63) | 153 | self | From your photo to your cart | HowTo | 657 |
| /pricing | TryOnU Pricing: Credit Packs, Store Plans & API (47) | 160 | self | Simple, pay-as-you-go pricing | site only | 527 |
| /faq | TryOnU FAQ: Virtual Try-On, Credits, Shopping & Stores (54) | 159 | self | TryOnU FAQ | FAQPage, BreadcrumbList | 1320 |
| /sell | Sell on TryOnU: Get Local Shoppers to Try Your Products (55) | 152 | self | Sell on TryOnU | site only | 544 |
| /earn | Invite Friends & Earn Free Try-On Credits / TryOnU (50) | 141 | self | Share TryOnU, earn free credits | site only | 404 |
| /extension | TryOnU Browser Extension: Try On Clothes From Any Shop (54) | 152 | self | Try on clothes from any shop, right in your browser | SoftwareApplication, FAQPage, BreadcrumbList | 639 |
| /find-look | Find the Look: Search Clothes by Photo / TryOnU (47) | 142 | self | Find the look from a photo | site only | 252 |
| /app | Get the TryOnU App on iPhone and Android (40) | 138 | self | TryOnU on your home screen | site only | 309 |
| /about | About TryOnU: AI Virtual Try-On for Everyone (44) | 141 | self | See it on you before you buy it | site only | 574 |
| /contact | Contact TryOnU (14) | 128 | self | We're here to help | site only | 359 |
| /sign-up | Create Your Free TryOnU Account (31) | 139 | self | Create your free TryOnU account | site only | 25 |
| /business/sign-up | Open Your Store on TryOnU (25) | 136 | self | Open your store on TryOnU | site only | 72 |
| /developers | TryOnU Developers: Virtual Try-On API (37) | 147 | self | Let shoppers see your products on themselves. | site only | 472 |
| /developers/docs | Virtual Try-On API Docs, Widget & Plugins / TryOnU (50) | 158 | self | Virtual try-on API | site only | 696 |
| /developers/sign-up | Try-On API: Create a Developer Account / TryOnU (47) | 141 | self | Start building with the TryOnU API | site only | 211 |
| /privacy | Privacy policy · TryOnU (23) | 88 | self | Privacy policy | site only | 888 |
| /terms | Terms of use · TryOnU (21) | 90 | self | Terms of use | site only | 1025 |
| /refunds | Refund policy · TryOnU (22) | 107 | self | Refund policy | site only | 422 |
| /photo-policy | Photo & data policy · TryOnU (28) | 79 | self | Photo & data policy | site only | 636 |
| /affiliate-disclosure | Affiliate disclosure · TryOnU (29) | 124 | self | Affiliate disclosure | site only | 432 |
| /virtual-try-on | Virtual Try-On for Clothes Online: See It on You / TryOnU (57) | 144 | self | Virtual try-on for clothes: see any outfit on your own photo | FAQPage, BreadcrumbList, HowTo | 690 |
| /ai-outfit-try-on | AI Outfit Try-On: Put a Whole Outfit on Your Photo / TryOnU (59) | 151 | self | AI outfit try-on: a complete look on you in one picture | FAQPage, BreadcrumbList, HowTo | 690 |
| /virtual-fitting-room | Online Virtual Fitting Room: Try Before You Buy / TryOnU (56) | 147 | self | A virtual fitting room on your phone | FAQPage, BreadcrumbList, HowTo | 651 |
| /ai-personal-stylist | AI Personal Stylist That Finds Real Products / TryOnU (53) | 157 | self | An AI personal stylist that picks real products for you | FAQPage, BreadcrumbList, HowTo | 680 |
| /bridal-dress-virtual-try-on | Bridal Dress & Lehenga Virtual Try-On / TryOnU (46) | 164 | self | Try on a bridal lehenga and wedding look on your own photo | FAQPage, BreadcrumbList, HowTo | 578 |
| /eastern-wear-virtual-try-on | Shalwar Kameez & Eastern Wear Virtual Try-On / TryOnU (53) | 137 | self | Virtual try-on for shalwar kameez, kurta and eastern wear | FAQPage, BreadcrumbList, HowTo | 616 |
| /try-on-glasses-watches-jewellery | Try On Sunglasses, Watches & Jewellery Online / TryOnU (54) | 142 | self | Try on sunglasses, watches and jewellery on your own photo | FAQPage, BreadcrumbList, HowTo | 566 |
| /virtual-try-on-for-shopify | Virtual Try-On for Shopify Stores / TryOnU (42) | 141 | self | Add virtual try-on to your Shopify store | FAQPage, BreadcrumbList | 493 |
| /virtual-try-on-for-woocommerce | Virtual Try-On Plugin for WordPress & WooCommerce / TryOnU (58) | 143 | self | Virtual try-on plugin for WordPress and WooCommerce | FAQPage, BreadcrumbList | 484 |
| /virtual-try-on-api | Virtual Try-On API for Fashion Apps & Stores / TryOnU (53) | 164 | self | Virtual try-on API: add AI try-on to your app or website | FAQPage, BreadcrumbList | 485 |
| /ai-clothes-changer | AI Clothes Changer: Change Clothes on Your Photo / TryOnU (57) | 144 | self | Change the clothes on your photo with AI, using real product | FAQPage, BreadcrumbList, HowTo | 725 |
| /virtual-try-on-app | Virtual Try-On App for Clothes on Your Phone / TryOnU (53) | 150 | self | A virtual try-on app that works on any phone | FAQPage, BreadcrumbList, HowTo | 702 |
| /eid-outfit-try-on | Eid Outfit Try-On: See Your Eid Dress on You / TryOnU (53) | 151 | self | See your Eid outfit on you before you buy | FAQPage, BreadcrumbList, HowTo | 642 |
| /groom-sherwani-virtual-try-on | Groom Sherwani Virtual Try-On: See It on You / TryOnU (53) | 140 | self | Try on a groom sherwani and wedding look on your own photo | FAQPage, BreadcrumbList, HowTo | 602 |
| /virtual-try-on-pakistan | Virtual Try-On in Pakistan: Try Clothes Online / TryOnU (55) | 153 | self | Try clothes on your photo before you buy online in Pakistan | FAQPage, BreadcrumbList, HowTo | 688 |
| /try-on-clothes-before-buying | Try On Clothes Before Buying Online: See Them on You / TryOnU (61) | 154 | self | How to see clothes on yourself before buying online | FAQPage, BreadcrumbList, HowTo | 608 |
| /wedding-guest-outfit-try-on | Wedding Guest Outfit Try-On: See the Look on You / TryOnU (57) | 143 | self | Wedding guest outfits: try the whole look on you first | FAQPage, BreadcrumbList, HowTo | 632 |
| /winter-outfit-try-on | Winter Outfit Ideas to Try On Your Own Photo / TryOnU (53) | 149 | self | Winter outfit ideas you can try on yourself | FAQPage, BreadcrumbList, HowTo | 618 |
| /virtual-try-on-for-fashion-brands | Virtual Try-On for Fashion Brands and Retailers / TryOnU (56) | 151 | self | Virtual try-on for fashion brands and online retailers | FAQPage, BreadcrumbList | 571 |
| /looks/{uuid} (36 pages, example) | Women's Look: Maroon Dress: Try It On You / TryOnU (50) | 158 | self | Women's Look: Maroon Dress | ItemList | 297 |
| /tryonu-fashion | Tryonu fashion: Shop & Try On / TryOnU (38) | 73 | self | Tryonu fashion | OnlineStore, BreadcrumbList | 267 |
| /zee-store | Zee Store: Shop & Try On / TryOnU (33) | 68 | self | Zee Store | OnlineStore, BreadcrumbList | 281 |
| /tryonu-fashion/products | All products: Tryonu fashion / TryOnU (37) | 84 | self | All products | site only | 262 |
| /zee-store/products | All products: Zee Store / TryOnU (32) | 79 | self | All products | site only | 432 |
| /zee-store/products/{id}, /tryonu-fashion/products/{id} | 29 product pages | | self | product name | Product (since 48152a4) | ~250 |
## Keyword map applied (second round)

| Page | Primary keyword | Title now | Main-content words |
|---|---|---|---|
| / | tryonu, AI virtual try-on | TryOnU: Try Clothes On Your Photo Before You Buy | 1,513 |
| /try-on-clothes-before-buying | try on clothes before buying online | Try On Clothes Before Buying Online, on Your Photo | 684 |
| /virtual-try-on | virtual try on clothes | Virtual Try-On for Clothes, Shoes and Bags | 703 |
| /ai-outfit-try-on | ai outfit try on | AI Outfit Try-On: See a Whole Look on You | 715 |
| /ai-clothes-changer | ai clothes changer | AI Clothes Changer With Real Shop Products | 539 |
| /virtual-fitting-room | virtual fitting room online | Online Virtual Fitting Room, From Your Phone | 468 |
| /ai-personal-stylist | ai personal stylist | Free AI Personal Stylist That Finds Real Clothes | 647 |
| /find-look | find outfit from picture | Find an Outfit From a Picture and Try It On | about 230 (tool runs in the browser) |
| /looks | ready outfit looks to try on | Ready Outfit Looks to Try On You | 1,235 |
| /looks/men | winter outfits for men uk | Men's Winter Outfits UK: Looks to Try On | 374 |
| /looks/women | winter coat outfits women | Women's Winter Coat Outfits to Try On | 321 |
| /looks/{slug} | the look's name + season | e.g. White Coat & White Heels: Women's Winter Look | 150 to 200 about the look |
| /winter-outfit-try-on | winter outfit ideas uk | Winter Outfit Ideas UK 2026: Try Them On You | 976 |
| /wedding-guest-outfit-try-on | wedding guest outfit winter | Winter Wedding Guest Outfits to Try On You | 614 |
| /eid-outfit-try-on | eid outfit ideas | Eid Outfit Ideas 2027: Try Them On First | 554 |
| /try-on-glasses-watches-jewellery | try on jewellery online | Try On Glasses, Watches and Jewellery Online | 382 |
| /virtual-try-on-app | tryonu app, virtual try on app | TryOnU App: Virtual Try-On on Your Phone | 517 |
| /pricing | tryonu pricing | TryOnU Pricing: First Outfit for $1 | 316 |
| /sell | online store with virtual try on | Your Own Store With Virtual Try-On, From $15 | 332 |
| /virtual-try-on-for-fashion-brands | ai virtual try on for brands | AI Virtual Try-On for Fashion Brands | 369 |
| /virtual-try-on-api | virtual try on api | Virtual Try-On API: Packs From $35 | 271 |
| /virtual-try-on-for-shopify | virtual try on for shopify | Virtual Try-On for Shopify Stores (Widget and API) | 342 |
| /virtual-try-on-for-woocommerce | virtual try on woocommerce | Virtual Try-On Plugin for WooCommerce | 273 |
| /christmas-party-outfit-try-on (new) | christmas party outfit ideas uk | Christmas Party Outfit Ideas UK: Try Them On | 762, live products |
| /modest-fashion-virtual-try-on (new) | abaya try on, modest fashion | Modest Fashion and Abaya Virtual Try-On | 738, live products |
| /guides (new) and six guides | see the plan | e.g. Amazon Try Before You Buy Alternative | 525 to 751 each |

Where the plan was changed, and why:
- **/virtual-try-on: "Free" is in the title** since new members get one free outfit (10 credits once their email is confirmed, once per person, commit 7a322e8). If the admin sets "Free credits on signup" back to 0, take "Free" out of this title and the copy that mentions the free outfit. /pricing is "First Outfit Free, Packs From $1".
- **/looks: "Ready Outfit Looks to Try On You", not "Winter Outfit Looks…".** "Winter" in the /looks title would compete with /winter-outfit-try-on and /looks/winter.
- **"ai outfit generator from photo" is on /ai-outfit-try-on, not /outfits.** /outfits is the signed-in outfit builder and is noindex.
- **Amazon:** no page claims Amazon products can be tried on. The guide and /try-on-clothes-before-buying say Amazon is coming soon, and explain Upload your own item, which works today with a product photo from any shop.
- **Brand spellings** (Try On U, TryOn U) appear once, in the "What is TryOnU?" answer, which is shown on / and /faq.
- **Business pages under 400 words** (/virtual-try-on-api, /woocommerce, /shopify, /fashion-brands, /sell, /pricing): improved titles only in this round; they need more copy next.

## Next (not in this branch)

1. More copy for the business pages under 400 words, and an H1 on the home page that carries "AI virtual try-on" (the hero is a design piece; change it with the designer).
2. GBP / CAD / AED price conversions by visitor country (needs a daily exchange-rate source; AED is pegged at 3.6725 per US dollar).
3. Test stores: noindex or remove (zee-store, tryonu-fashion).
4. Image optimisation for look pictures (WebP/AVIF, srcset).
