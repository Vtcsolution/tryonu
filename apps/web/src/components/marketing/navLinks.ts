/** The site's navigation, shared by the header, the phone menu and the footer.
 * Few links, plain words: someone aged 10 or 90 should know at once where each goes. */

/** highlight: a softly glowing link, for the places we most want people to find */
export type NavItem = { label: string; href: string; highlight?: boolean };
export type NavGroup = { label: string; items: NavItem[] };

/** The header's links on computers. */
export const MAIN: NavItem[] = [
  { label: "Try on", href: "/try" },
  { label: "Ready looks", href: "/looks", highlight: true },
  { label: "Find by photo", href: "/find-look" },
  { label: "AI Stylist", href: "/stylist" },
  { label: "Community", href: "/community" },
  { label: "Pricing", href: "/pricing" },
  { label: "For shops", href: "/sell", highlight: true },
];

/** The footer's columns (and the phone menu). */
export const GROUPS: NavGroup[] = [
  {
    label: "TryOnU",
    items: [
      { label: "Try on", href: "/try" },
      { label: "Ready looks", href: "/looks", highlight: true },
      { label: "Find by photo", href: "/find-look" },
      { label: "AI Stylist", href: "/stylist" },
      { label: "Build an outfit", href: "/outfits" },
      { label: "My clothes", href: "/wardrobe" },
      { label: "Get the app", href: "/app" },
    ],
  },
  {
    label: "Community",
    items: [
      { label: "Community", href: "/community" },
      { label: "Style challenges", href: "/community/challenges" },
      { label: "Invite & earn", href: "/earn" },
    ],
  },
  {
    label: "For shops",
    items: [
      { label: "Sell on TryOnU", href: "/sell", highlight: true },
      { label: "My store", href: "/business" },
      { label: "For developers", href: "/developers" },
      { label: "Browser extension", href: "/extension" },
    ],
  },
  {
    label: "Help",
    items: [
      { label: "How it works", href: "/how-it-works" },
      { label: "Pricing", href: "/pricing" },
      { label: "Help & FAQ", href: "/faq" },
      { label: "Contact", href: "/contact" },
      { label: "About", href: "/about" },
    ],
  },
];

export const LEGAL: NavItem[] = [
  { label: "Privacy", href: "/privacy" },
  { label: "Terms", href: "/terms" },
  { label: "Refunds", href: "/refunds" },
  { label: "Photo policy", href: "/photo-policy" },
  { label: "Affiliate disclosure", href: "/affiliate-disclosure" },
];
