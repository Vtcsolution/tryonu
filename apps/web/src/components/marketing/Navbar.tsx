import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";
import { Button } from "@/components/ui/Button";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { AccountMenu } from "@/components/marketing/AccountMenu";
import { MobileNav } from "@/components/marketing/MobileNav";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { LensHeaderButton } from "@/components/lens/LensHeaderButton";
import { PhoneAccount } from "@/components/app/PhoneAccount";
import { BUSINESS, COMPANY, PRODUCT, TOP_LINKS, type NavGroup } from "@/components/marketing/navLinks";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-line/70 bg-paper/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 tu-container items-center justify-between gap-3 lg:h-[72px] lg:gap-4">
        <Logo size={28} />

        <nav aria-label="Main" className="hidden items-center gap-6 whitespace-nowrap xl:flex 2xl:gap-8">
          <NavMenu group={PRODUCT} />
          <NavMenu group={BUSINESS} />
          {TOP_LINKS.map((l) => (
            <NavLink key={l.href} href={l.href}>
              {l.label}
            </NavLink>
          ))}
          <NavMenu group={COMPANY} />
        </nav>

        <div className="flex items-center gap-1 sm:gap-2 lg:gap-3">
          <span className="hidden lg:inline-flex">
            <ThemeToggle />
          </span>
          <LensHeaderButton />
          <NotificationBell />
          <span className="hidden lg:block">
            <AccountMenu />
          </span>
          <PhoneAccount />
          <span className="hidden lg:inline-flex">
            <Button href="/try" size="sm" className="whitespace-nowrap">
              Try it now <span aria-hidden="true">→</span>
            </Button>
          </span>
          <MobileNav />
        </div>
      </div>
    </header>
  );
}

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      prefetch={false}
      className="group/nl relative text-[15.5px] font-medium text-ink transition-colors duration-200 hover:text-sage-deep"
    >
      {children}
      <span className="absolute -bottom-1.5 left-0 h-px w-full origin-left scale-x-0 bg-sage transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover/nl:scale-x-100" />
    </Link>
  );
}

function NavMenu({ group }: { group: NavGroup }) {
  return (
    <div className="group relative">
      <button
        type="button"
        className="flex items-center gap-1.5 text-[15.5px] font-medium text-ink transition-colors duration-200 group-hover:text-sage-deep group-focus-within:text-sage-deep"
        aria-haspopup="true"
      >
        {group.label}
        <svg
          width="11"
          height="11"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
          className="mt-0.5 transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:rotate-180 group-focus-within:rotate-180"
        >
          <path d="M2.5 4.5 6 8l3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* pt-3 keeps a hover bridge between the label and the panel */}
      <div className="invisible absolute left-1/2 top-full z-50 -translate-x-1/2 translate-y-1 pt-3 opacity-0 transition-[opacity,transform] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100">
        <div className="w-[300px] rounded-2xl border border-line bg-surface p-2 shadow-lift">
          {group.items.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              prefetch={false}
              className="block rounded-xl px-3 py-2.5 transition-colors duration-200 hover:bg-paper-2"
            >
              <span className="block text-[15px] font-semibold text-ink">{l.label}</span>
              {l.hint && <span className="mt-0.5 block text-[13px] leading-snug text-muted">{l.hint}</span>}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
