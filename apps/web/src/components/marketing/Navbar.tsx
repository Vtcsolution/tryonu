import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";
import { Button } from "@/components/ui/Button";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { AccountMenu } from "@/components/marketing/AccountMenu";

type MenuLink = { label: string; href: string; hint?: string };

const PRODUCT_LINKS: MenuLink[] = [
  { label: "Try-on studio", href: "/try", hint: "See a look on you" },
  { label: "AI Stylist", href: "/stylist", hint: "Ask for a recommendation" },
  { label: "Outfit builder", href: "/outfits", hint: "Combine real products" },
  { label: "My wardrobe", href: "/wardrobe", hint: "What you already own" },
  { label: "Saved looks", href: "/saved", hint: "Your lookbook" },
  { label: "Marketplaces", href: "/#marketplaces", hint: "Amazon, eBay, Flipkart, Daraz" },
  { label: "How it works", href: "/how-it-works", hint: "The full flow" },
  { label: "Features", href: "/#features", hint: "What's inside" },
];

const COMPANY_LINKS: MenuLink[] = [
  { label: "About", href: "#" },
  { label: "Blog", href: "#" },
  { label: "Careers", href: "#" },
  { label: "Contact", href: "#" },
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-line/70 bg-paper/80 backdrop-blur-xl">
      <div className="mx-auto flex h-[72px] w-[min(1180px,calc(100%-42px))] items-center justify-between">
        <Logo size={30} />

        <nav className="hidden items-center gap-9 md:flex">
          <NavMenu label="Product">{PRODUCT_LINKS}</NavMenu>
          <NavLink href="/how-it-works">How it works</NavLink>
          <NavMenu label="Company">{COMPANY_LINKS}</NavMenu>
        </nav>

        <div className="flex items-center gap-2 sm:gap-4">
          <ThemeToggle />
          <AccountMenu />

          <Button href="/try" size="sm">
            Try it now <span aria-hidden="true">→</span>
          </Button>
        </div>
      </div>
    </header>
  );
}

/* --- nav pieces: serif type, ink→muted on hover, carets that flip --- */

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="group/nl relative font-display text-[15px] tracking-[-0.01em] text-ink transition-colors duration-200 hover:text-faint"
    >
      {children}
      <span className="absolute -bottom-1.5 left-0 h-px w-full origin-left scale-x-0 bg-faint transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover/nl:scale-x-100" />
    </Link>
  );
}

function NavMenu({ label, children }: { label: string; children: MenuLink[] }) {
  return (
    <div className="group relative">
      <button
        type="button"
        className="flex items-center gap-1.5 font-display text-[15px] tracking-[-0.01em] text-ink transition-colors duration-200 group-hover:text-faint group-focus-within:text-faint"
        aria-haspopup="true"
      >
        {label}
        <svg
          width="11"
          height="11"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
          className="mt-0.5 transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:rotate-180 group-focus-within:rotate-180"
        >
          <path
            d="M2.5 4.5 6 8l3.5-3.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {/* pt-3 keeps a hover bridge between trigger and panel */}
      <div className="invisible absolute left-1/2 top-full z-50 -translate-x-1/2 translate-y-1 pt-3 opacity-0 transition-[opacity,transform] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100">
        <div className="min-w-[248px] rounded-2xl border border-line bg-surface p-2 shadow-lift">
          {children.map((l) => (
            <Link
              key={l.label}
              href={l.href}
              className="block rounded-xl px-3 py-2.5 transition-colors duration-200 hover:bg-paper-2"
            >
              <span className="block font-display text-[14px] text-ink">
                {l.label}
              </span>
              {l.hint && (
                <span className="mt-0.5 block text-[12px] text-muted">
                  {l.hint}
                </span>
              )}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
