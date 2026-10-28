import Link from "next/link";
import { ContactForm } from "@/components/content/ContactForm";
import { ContentPage } from "@/components/content/ContentPage";
import { HelpWhatsApp } from "@/components/whatsapp/WhatsApp";
import { isDevPortal } from "@/lib/devLinks";
import { pageMeta } from "@/lib/seo";
import { EMAIL_LIST } from "@/lib/contactEmails";

export const metadata = pageMeta({
  title: "Contact TryOnU",
  description:
    "Questions about try-ons, credits, selling on TryOnU, the developer API or your data? Send us a message and we'll reply by email.",
  path: "/contact",
  keywords: [],
});

const HELP: { title: string; text: string; href: string; link: string }[] = [
  { title: "Prices and credits", text: "What a try-on costs and the credit packs.", href: "/pricing", link: "See pricing" },
  { title: "Selling on TryOnU", text: "Store plans and how to open a store.", href: "/sell", link: "Sell on TryOnU" },
  { title: "Developers", text: "API, website widget and plugins.", href: "/developers/docs", link: "API docs" },
  { title: "Your photos and data", text: "What we keep and how to delete it.", href: "/photo-policy", link: "Photo & data policy" },
];

export default function ContactPage() {
  return (
    <ContentPage
      kicker="Contact"
      title="We're here to help"
      intro="Send us a message and we'll reply by email, usually within one to two working days."
    >
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="rounded-[24px] border border-line bg-surface p-6 md:p-8">
          <ContactForm />
        </div>
        <aside>
          <div className="mb-6 empty:hidden">
            <HelpWhatsApp />
          </div>
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-faint">Email us</p>
          <div className="mb-6 mt-3 space-y-2">
            {EMAIL_LIST.map((e) => (
              <a
                key={e.email}
                href={`mailto:${e.email}`}
                className="block rounded-[18px] border border-line bg-surface p-4 transition-colors hover:border-line-strong"
              >
                <p className="text-[16px] font-semibold text-ink">{e.label}</p>
                <p className="mt-0.5 text-[14.5px] text-muted">{e.text}</p>
                <p className="mt-1.5 text-[15px] font-semibold text-sage-deep">{e.email}</p>
              </a>
            ))}
          </div>
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-faint">Quick answers</p>
          <div className="mt-3 space-y-3">
            {HELP.map((h) => (
              <Link
                key={h.href}
                href={h.href}
                className="block rounded-[18px] border border-line bg-surface p-4 transition-colors hover:border-line-strong"
                {...(isDevPortal(h.href) ? { target: "_blank", rel: "noopener" } : {})}
              >
                <p className="text-[16px] font-semibold text-ink">{h.title}</p>
                <p className="mt-0.5 text-[14.5px] text-muted">{h.text}</p>
                <p className="mt-2 text-[14.5px] font-semibold text-sage-deep">{h.link} →</p>
              </Link>
            ))}
          </div>
        </aside>
      </div>
    </ContentPage>
  );
}
