/** TryOnU's email addresses, shown on the website (the same as Admin → Settings → Email). */
export const EMAILS = {
  support: "support@tryonu.app",
  sales: "sales@tryonu.app",
  billing: "billing@tryonu.app",
} as const;

export const EMAIL_LIST: { label: string; text: string; email: string }[] = [
  { label: "Help", text: "Try-ons, credits and your account", email: EMAILS.support },
  { label: "Shops and partners", text: "Selling on TryOnU, brands, press", email: EMAILS.sales },
  { label: "Payments", text: "Receipts, refunds and billing", email: EMAILS.billing },
];
