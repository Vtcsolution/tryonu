import Link from "next/link";
import type { DeveloperCreditPack } from "@/lib/api/types";
import { OldConsoleLinks } from "./OldConsoleLinks";

const REQUEST = `curl -X POST https://api.tryonu.app/api/v1/public/tryons \\
  -H "Authorization: Bearer $TRYONU_API_KEY" \\
  -F person_image=@customer.jpg \\
  -F garment_image=@dress.jpg`;

const RESPONSE = `{
  "id": "tr_8f2c…",
  "status": "completed",
  "result_image_url": "https://…/result.jpg",
  "credits_used": 1
}`;

const WAYS: { tag: string; title: string; text: string; href: string; cta: string }[] = [
  {
    tag: "REST API",
    title: "Server API",
    text: "Send a customer photo and a product photo from any language: cURL, Node, Python, PHP. Get back the customer wearing it.",
    href: "/developers/docs#code",
    cta: "See the code",
  },
  {
    tag: "No code",
    title: "Website widget",
    text: "Paste two lines into your product page. A “Try it on” button appears; shoppers add a photo and see themselves in it.",
    href: "/developers/docs#widget",
    cta: "Add the button",
  },
  {
    tag: "Plugins",
    title: "WordPress, WooCommerce & Shopify",
    text: "Install the plugin or paste the Shopify snippet. Your product pictures are used automatically.",
    href: "/developers/docs#widget",
    cta: "Set it up",
  },
];

const STEPS: { title: string; text: string }[] = [
  { title: "Create your account", text: "Email and password, then name your project. Free, no card needed." },
  { title: "Get a key", text: "A secret key for your server, or a website key locked to your own domains." },
  { title: "Make your first try-on", text: "Buy a credit pack and call the API, or paste the widget into your shop." },
];

const FACTS: [string, string][] = [
  ["1 credit", "per try-on"],
  ["Free", "if a try-on fails"],
  ["Never", "do credits expire"],
  ["20–60 s", "per try-on"],
];

function price(cents: number, currency: string) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase() }).format(cents / 100);
}

/** /developers: the developer platform's home page. Anyone can read it; the console is at /developers/console. */
export function DevHome({ packs }: { packs: DeveloperCreditPack[] }) {
  const cheapest = packs.length ? Math.min(...packs.map((p) => p.price_cents / Math.max(1, p.tryons))) : null;
  const currency = packs[0]?.currency ?? "usd";

  return (
    <>
      <OldConsoleLinks />
      {/* hero */}
      <section className="relative overflow-hidden bg-[#0d1210] text-white">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:linear-gradient(#fff_1px,transparent_1px),linear-gradient(90deg,#fff_1px,transparent_1px)] [background-size:44px_44px]"
        />
        <div aria-hidden="true" className="pointer-events-none absolute -right-40 -top-40 h-[520px] w-[520px] rounded-full bg-[#7d917a]/25 blur-[120px]" />
        <div className="relative mx-auto grid w-[min(1280px,calc(100%-32px))] items-center gap-12 py-16 md:py-24 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <p className="font-mono text-[12.5px] font-semibold uppercase tracking-[0.16em] text-[#b9cdb5]">Virtual try-on API</p>
            <h1 className="mt-4 text-[clamp(34px,5.2vw,58px)] font-semibold leading-[1.05] tracking-[-0.03em]">
              Let shoppers see your products <span className="text-[#b9cdb5]">on themselves.</span>
            </h1>
            <p className="mt-5 max-w-xl text-[17.5px] leading-relaxed text-white/70">
              Add AI try-on to your website or app with one simple API, a no-code widget, or a plugin. Pay only for the try-ons you use
              {cheapest !== null ? `: from ${price(Math.round(cheapest), currency)} each.` : "."}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/developers/sign-up" className="tu-press rounded-lg bg-[#7d917a] px-6 py-3.5 text-[16px] font-semibold text-[#0d1210] hover:bg-[#93a88f]">
                Get your API key →
              </Link>
              <Link href="/developers/docs" className="rounded-lg border border-white/20 px-6 py-3.5 text-[16px] font-semibold text-white hover:bg-white/5">
                Read the docs
              </Link>
            </div>
          </div>
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#070a09] shadow-2xl">
            <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              <span className="ml-3 font-mono text-[12.5px] text-white/45">POST /public/tryons</span>
            </div>
            <pre className="overflow-x-auto p-5 font-mono text-[13px] leading-relaxed text-[#d7e3d4]">
              <code>{REQUEST}</code>
            </pre>
            <div className="border-t border-white/10 px-4 py-2 font-mono text-[12px] text-white/40">200 OK · response</div>
            <pre className="overflow-x-auto p-5 pt-3 font-mono text-[13px] leading-relaxed text-[#b9cdb5]">
              <code>{RESPONSE}</code>
            </pre>
          </div>
        </div>
        <div className="relative border-t border-white/10">
          <dl className="mx-auto grid w-[min(1280px,calc(100%-32px))] grid-cols-2 md:grid-cols-4">
            {FACTS.map(([big, small]) => (
              <div key={small} className="border-white/10 py-6 md:border-l md:px-6 md:first:border-l-0 md:first:pl-0">
                <dt className="text-[24px] font-semibold">{big}</dt>
                <dd className="text-[14px] text-white/55">{small}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ways to add it */}
      <section className="mx-auto w-[min(1280px,calc(100%-32px))] py-16 md:py-20">
        <p className="font-mono text-[12.5px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Choose how</p>
        <h2 className="mt-2 text-[clamp(26px,3.4vw,38px)] font-semibold tracking-[-0.02em] text-ink">Three ways to add try-on</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {WAYS.map((w) => (
            <Link key={w.title} href={w.href} className="group flex flex-col rounded-2xl border border-line bg-surface p-6 transition-colors hover:border-sage">
              <span className="w-fit rounded-md bg-sage/10 px-2 py-1 font-mono text-[12px] font-semibold uppercase tracking-[0.08em] text-sage-deep">{w.tag}</span>
              <span className="mt-4 text-[20px] font-semibold text-ink">{w.title}</span>
              <span className="mt-2 flex-1 text-[15px] leading-relaxed text-muted">{w.text}</span>
              <span className="mt-5 text-[15px] font-semibold text-sage-deep group-hover:underline">{w.cta} →</span>
            </Link>
          ))}
        </div>
      </section>

      {/* steps */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto w-[min(1280px,calc(100%-32px))] py-16 md:py-20">
          <p className="font-mono text-[12.5px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Get started</p>
          <h2 className="mt-2 text-[clamp(26px,3.4vw,38px)] font-semibold tracking-[-0.02em] text-ink">Live in three steps</h2>
          <ol className="mt-8 grid gap-6 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="relative rounded-2xl border border-line bg-paper p-6">
                <span className="grid h-10 w-10 place-items-center rounded-lg bg-[#0d1210] font-mono text-[16px] font-semibold text-[#b9cdb5]">{i + 1}</span>
                <p className="mt-4 text-[18px] font-semibold text-ink">{s.title}</p>
                <p className="mt-1.5 text-[15px] leading-relaxed text-muted">{s.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* pricing */}
      <section id="pricing" className="mx-auto w-[min(1280px,calc(100%-32px))] scroll-mt-20 py-16 md:py-20">
        <p className="font-mono text-[12.5px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Pricing</p>
        <h2 className="mt-2 text-[clamp(26px,3.4vw,38px)] font-semibold tracking-[-0.02em] text-ink">Pay per try-on. No monthly fee.</h2>
        <p className="mt-3 max-w-2xl text-[16px] text-muted">
          Buy a pack of credits. Each try-on uses one; a try-on that fails gives it back. Credits never expire.
        </p>
        {packs.length > 0 ? (
          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {packs.map((p, i) => {
              const best = i === packs.length - 1 && packs.length > 1;
              return (
                <div key={p.id} className={`flex flex-col rounded-2xl border p-6 ${best ? "border-sage bg-sage/[0.06]" : "border-line bg-surface"}`}>
                  <div className="flex items-center justify-between">
                    <p className="text-[17px] font-semibold text-ink">{p.name}</p>
                    {best && <span className="rounded-md bg-sage px-2 py-0.5 text-[12px] font-semibold text-white">Best value</span>}
                  </div>
                  <p className="mt-4 text-[34px] font-semibold tracking-[-0.02em] text-ink">{price(p.price_cents, p.currency)}</p>
                  <p className="text-[14.5px] text-muted">
                    {p.tryons.toLocaleString()} try-ons · {price(Math.round(p.price_cents / Math.max(1, p.tryons)), p.currency)} each
                  </p>
                  <Link
                    href="/developers/console#credits"
                    className={`mt-6 rounded-lg py-3 text-center text-[15px] font-semibold ${best ? "bg-sage text-white" : "border border-line-strong text-ink hover:border-sage"}`}
                  >
                    Buy in the console
                  </Link>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="mt-6 text-[15px] text-muted">Packs are shown in the console.</p>
        )}
      </section>

      {/* keys and safety */}
      <section className="border-t border-line bg-surface">
        <div className="mx-auto grid w-[min(1280px,calc(100%-32px))] gap-8 py-16 md:grid-cols-3">
          {[
            ["Two kinds of key", "A secret key (tou_sk_…) for your server, and a website key (tou_pk_…) that only works on the domains you choose."],
            ["Keep your results", "Each finished picture comes back as a link. Download it and keep it on your side: the link expires."],
            ["Fair limits", "Each website visitor can make a few try-ons an hour, so nobody can spend your credits for you."],
          ].map(([title, text]) => (
            <div key={title}>
              <p className="text-[17px] font-semibold text-ink">{title}</p>
              <p className="mt-2 text-[15px] leading-relaxed text-muted">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* last call */}
      <section className="bg-[#0d1210] text-white">
        <div className="mx-auto flex w-[min(1280px,calc(100%-32px))] flex-wrap items-center justify-between gap-6 py-14">
          <div>
            <p className="text-[clamp(24px,3vw,32px)] font-semibold tracking-[-0.02em]">Ready to build?</p>
            <p className="mt-1 text-[16px] text-white/60">Create your account and make your first try-on today.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/developers/sign-up" className="tu-press rounded-lg bg-[#7d917a] px-6 py-3.5 text-[16px] font-semibold text-[#0d1210] hover:bg-[#93a88f]">
              Get your API key →
            </Link>
            <Link href="/contact" className="rounded-lg border border-white/20 px-6 py-3.5 text-[16px] font-semibold hover:bg-white/5">
              Talk to us
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
