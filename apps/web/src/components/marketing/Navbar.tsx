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
import { PhoneTitle } from "@/components/app/PhoneTitle";
import { MAIN } from "@/components/marketing/navLinks";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-line/70 bg-paper/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 tu-container items-center justify-between gap-3 lg:h-[72px] lg:gap-4">
        <span className="hidden lg:inline-flex">
          <Logo size={30} />
        </span>
        <PhoneTitle />

        <nav aria-label="Main" className="hidden items-center gap-6 whitespace-nowrap xl:flex 2xl:gap-8">
          {MAIN.map((l) => (
            <NavLink key={l.href} href={l.href}>
              {l.label}
            </NavLink>
          ))}
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
