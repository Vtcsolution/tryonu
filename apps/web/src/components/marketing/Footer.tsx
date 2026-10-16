import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { BUSINESS, COMPANY, LEGAL, PRODUCT, type NavItem } from "@/components/marketing/navLinks";

const COLS: { heading: string; links: NavItem[] }[] = [
  {
    heading: "Shoppers",
    links: [...PRODUCT.items.filter((l) => l.href !== "/#marketplaces"), { label: "Pricing", href: "/pricing" }, { label: "How it works", href: "/how-it-works" }],
  },
  {
    heading: "Business",
    links: [
      ...BUSINESS.items,
      { label: "Create a store account", href: "/business/sign-up" },
      { label: "Create a developer account", href: "/developers/sign-up" },
    ],
  },
  {
    heading: "Earn & company",
    links: [
      { label: "Invite friends & earn credits", href: "/earn" },
      ...COMPANY.items.filter((l) => l.href !== "/earn"),
    ],
  },
  { heading: "Legal", links: LEGAL },
];

export function Footer() {
  return (
    <footer className="border-t border-line bg-paper-2">
      <div className="mx-auto w-[min(1600px,calc(100%-32px))] py-14">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr_1fr_1fr]">
          <div className="sm:col-span-2 lg:col-span-1">
            <Logo size={30} />
            <p className="mt-4 max-w-xs font-display text-[18px] italic text-ink-soft">Try it. See you. Shop it.</p>
            <p className="mt-3 max-w-sm text-[14.5px] leading-relaxed text-muted">
              See real products on your own photo before you buy, then shop from the original store. For shoppers, stores and
              developers.
            </p>
            <Link
              href="/try"
              className="mt-5 inline-flex min-h-[44px] items-center rounded-full bg-sage px-5 text-[15px] font-semibold text-white hover:bg-sage-deep"
            >
              Try it now →
            </Link>
          </div>

          {COLS.map((col) => (
            <div key={col.heading}>
              <h4 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-faint">{col.heading}</h4>
              <ul className="mt-4 space-y-2.5 text-[15px] text-ink-soft">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} prefetch={false} className="transition-colors hover:text-ink">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-3 border-t border-line pt-6 text-[13.5px] text-faint lg:flex-row lg:items-center lg:justify-between">
          <span>© {new Date().getFullYear()} TryOnU. All rights reserved.</span>
          <span className="max-w-3xl lg:text-right">
            Try-on pictures are made with AI and are a preview: fit, size and colour can differ in real life. TryOnU may earn a
            commission when you buy through its shop links, at no extra cost to you.{" "}
            <Link href="/affiliate-disclosure" className="underline hover:text-ink-soft">
              Learn more
            </Link>
            .
          </span>
        </div>
      </div>
    </footer>
  );
}
