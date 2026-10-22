import { isDevPortal } from "@/lib/devLinks";
import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { SOCIAL_LINKS, type SocialName } from "@/lib/seo";
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
            <div className="mt-6 flex items-center gap-2" aria-label="TryOnU on social media">
              {SOCIAL_LINKS.map((s) => (
                <a
                  key={s.name}
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer me"
                  aria-label={`TryOnU on ${s.name} (${s.handle})`}
                  title={`${s.name}: ${s.handle}`}
                  className="grid h-11 w-11 place-items-center rounded-full border border-line-strong text-ink-soft transition-colors hover:border-ink/40 hover:text-ink"
                >
                  <SocialIcon name={s.name} />
                </a>
              ))}
            </div>
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
            <span>© {new Date().getFullYear()} TryOnU</span>
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

function SocialIcon({ name }: { name: SocialName }) {
  const common = { width: 18, height: 18, viewBox: "0 0 24 24", "aria-hidden": true } as const;
  if (name === "LinkedIn") {
    return (
      <svg {...common} fill="currentColor">
        <rect x="3.5" y="9" width="3.6" height="11" rx=".4" />
        <circle cx="5.3" cy="5.3" r="2.1" />
        <path d="M9.6 9h3.4v1.6c.6-1 1.8-1.9 3.6-1.9 3 0 3.9 1.9 3.9 4.8V20h-3.6v-5.8c0-1.4-.3-2.6-1.8-2.6s-2 1.1-2 2.6V20H9.6V9z" />
      </svg>
    );
  }
  if (name === "Instagram") {
    return (
      <svg {...common} fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
      </svg>
    );
  }
  if (name === "TikTok") {
    return (
      <svg {...common} fill="currentColor">
        <path d="M16.6 3c.4 2.2 1.8 3.7 4 3.9v3.2c-1.5 0-2.8-.4-4-1.2v6.3c0 3.3-2.5 5.8-5.8 5.8S5 18.5 5 15.2c0-3.4 2.9-6 6.4-5.7v3.3c-1.5-.3-3 .8-3 2.4 0 1.4 1.1 2.5 2.4 2.5 1.4 0 2.6-1.1 2.6-2.6V3h3.2z" />
      </svg>
    );
  }
  return (
    <svg {...common} fill="currentColor">
      <path d="M13.5 21v-7.5h2.6l.4-3h-3V8.6c0-.9.3-1.5 1.5-1.5h1.6V4.4c-.3 0-1.2-.1-2.3-.1-2.3 0-3.8 1.4-3.8 3.9v2.3H8v3h2.5V21h3z" />
    </svg>
  );
}
