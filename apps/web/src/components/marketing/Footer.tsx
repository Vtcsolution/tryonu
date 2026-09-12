import { Logo } from "@/components/ui/Logo";

const COLS: { heading: string; links: { label: string; href: string }[] }[] = [
  {
    heading: "Product",
    links: [
      { label: "How it works", href: "/how-it-works" },
      { label: "Try-on studio", href: "/try" },
      { label: "Marketplaces", href: "/#marketplaces" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "#" },
      { label: "Careers", href: "#" },
      { label: "Blog", href: "#" },
      { label: "Contact", href: "#" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { label: "Privacy", href: "#" },
      { label: "Terms", href: "#" },
      { label: "Photo & data policy", href: "#" },
      { label: "Affiliate disclosure", href: "#" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-line bg-paper-2">
      <div className="mx-auto w-[min(1180px,calc(100%-42px))] py-14">
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Logo size={30} />
            <p className="mt-4 max-w-xs font-display text-[18px] italic text-ink-soft">
              Try It. See You. Shop It.
            </p>
            <p className="mt-3 max-w-xs text-[13px] leading-relaxed text-muted">
              AI-powered virtual fashion shopping. Try real products on your own
              photos, then buy from the original retailer.
            </p>
          </div>

          {COLS.map((col) => (
            <div key={col.heading}>
              <h4 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-faint">
                {col.heading}
              </h4>
              <ul className="mt-4 space-y-2.5 text-[13.5px] text-ink-soft">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a href={l.href} className="transition-colors hover:text-ink">
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-3 border-t border-line pt-6 text-[12px] text-faint sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} TryOnU. All rights reserved.</span>
          <span>
            TryOnU is an independent try-on service and is not affiliated with the
            retailers shown. Photography via{" "}
            <a
              href="https://unsplash.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline transition-colors hover:text-ink-soft"
            >
              Unsplash
            </a>
            .
          </span>
        </div>
      </div>
    </footer>
  );
}
