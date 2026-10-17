/** The site's navigation, shared by the header, the phone menu and the footer. */

export type NavItem = { label: string; href: string; hint?: string };
export type NavGroup = { label: string; items: NavItem[] };

export const PRODUCT: NavGroup = {
  label: "Product",
  items: [
    { label: "Try-on studio", href: "/try", hint: "See any product on your own photo" },
    { label: "AI Stylist", href: "/stylist", hint: "Describe a look, get real products" },
    { label: "Outfit builder", href: "/outfits", hint: "Put several pieces together" },
    { label: "My wardrobe", href: "/wardrobe", hint: "Try with clothes you own" },
    { label: "Saved looks", href: "/saved", hint: "Your lookbook, ready to share" },
    { label: "Browser extension", href: "/extension", hint: "Try on from eBay, AliExpress, any shop" },
    { label: "Marketplaces", href: "/#marketplaces", hint: "eBay, AliExpress, brand stores and local shops" },
  ],
};

export const BUSINESS: NavGroup = {
  label: "For business",
  items: [
    { label: "Sell on TryOnU", href: "/sell", hint: "Open a store, reach shoppers near you" },
    { label: "Store dashboard", href: "/business", hint: "Products, plans and shopper try-ons" },
    { label: "Store extension", href: "/extension#stores", hint: "Add products from any page in one click" },
    { label: "Try-on API", href: "/developers", hint: "Virtual try-on for your app or site" },
    { label: "API docs & plugins", href: "/developers/docs", hint: "Shopify, WordPress, any website" },
  ],
};

export const COMPANY: NavGroup = {
  label: "Company",
  items: [
    { label: "About TryOnU", href: "/about", hint: "Who we are and what we do" },
    { label: "Questions & answers", href: "/faq", hint: "How it works, prices, privacy" },
    { label: "Invite & earn", href: "/earn", hint: "Earn credits when friends join" },
    { label: "Contact", href: "/contact", hint: "Questions, stores, partnerships" },
  ],
};

export const TOP_LINKS: NavItem[] = [
  { label: "Community", href: "/community" },
  { label: "Pricing", href: "/pricing" },
  { label: "How it works", href: "/how-it-works" },
];

export const LEGAL: NavItem[] = [
  { label: "Privacy policy", href: "/privacy" },
  { label: "Terms of use", href: "/terms" },
  { label: "Photo & data policy", href: "/photo-policy" },
  { label: "Affiliate disclosure", href: "/affiliate-disclosure" },
];
