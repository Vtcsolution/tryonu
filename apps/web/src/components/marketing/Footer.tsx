import { isDevPortal } from "@/lib/devLinks";
import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { copyrightLine } from "@/lib/seo";
import { SocialLinks } from "@/components/marketing/SocialLinks";
import { EMAILS } from "@/lib/contactEmails";
import { LANDINGS } from "@/lib/seoContent";
import { GROUPS, LEGAL } from "@/components/marketing/navLinks";

export function Footer() {
  return (
    <footer className="hidden border-t border-line bg-paper-2 lg:block">
      <div className="tu-container py-14">
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
            <SocialLinks className="mt-6" />
            <a href={`mailto:${EMAILS.support}`} className="mt-4 inline-block text-[15px] font-semibold text-sage-deep hover:underline">
              {EMAILS.support}
            </a>
          </div>

          {GROUPS.map((col) => (
            <div key={col.label}>
              <h4 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-faint">{col.label}</h4>
              <ul className="mt-4 space-y-2.5 text-[15px] text-ink-soft">
                {col.items.map((l) => (
                  <li key={l.href}>
                    <Link
                      href={l.href}
                      prefetch={false}
                      className="transition-colors hover:text-ink"
                      {...(isDevPortal(l.href) ? { target: "_blank", rel: "noopener" } : {})}
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* the topic pages, linked from every page */}
        <div className="mt-12 border-t border-line pt-6">
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-faint">Popular</p>
          <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-[14.5px] text-ink-soft">
            {LANDINGS.map((l) => (
              <li key={l.slug}>
                <Link href={`/${l.slug}`} prefetch={false} className="transition-colors hover:text-ink">
                  {l.kicker}
                </Link>
              </li>
            ))}
            <li>
              <Link href="/faq" prefetch={false} className="transition-colors hover:text-ink">
                FAQ
              </Link>
            </li>
          </ul>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-line pt-6 text-[13.5px] text-faint lg:flex-row lg:items-center lg:justify-between">
          <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span>{copyrightLine()}</span>
            {LEGAL.map((l) => (
              <Link key={l.href} href={l.href} prefetch={false} className="hover:text-ink-soft">
                {l.label}
              </Link>
            ))}
          </span>
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
