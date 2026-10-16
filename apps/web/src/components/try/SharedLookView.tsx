import { ProductCard } from "@/components/product/ProductCard";
import { Button } from "@/components/ui/Button";
import type { SharedLook } from "@/lib/api/types";

/** What anyone with a shared look's link sees: the picture, the products and where to buy them. */
export function SharedLookView({ look }: { look: SharedLook }) {
  const total =
    look.products.length > 0 && new Set(look.products.map((p) => p.currency.toLowerCase())).size === 1
      ? look.products.reduce((sum, p) => sum + p.price_cents, 0)
      : null;
  const currency = look.products[0]?.currency ?? "usd";
  return (
    <section className="mx-auto w-[min(1280px,calc(100%-42px))] py-10 md:py-14">
      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">A look made with TryOnU</p>
      <h1 className="mt-2 font-display text-[clamp(28px,4.4vw,44px)] leading-tight text-ink">{look.title}</h1>
      {total !== null && (
        <p className="mt-2 text-[16px] text-ink-soft">
          {look.products.length === 1 ? "1 piece" : `${look.products.length} pieces`} ·{" "}
          {new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase() }).format(total / 100)}
        </p>
      )}

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)]">
        <figure className="overflow-hidden rounded-[28px] border border-line bg-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={look.image_url} alt={`AI try-on: ${look.title}`} className="h-auto w-full" />
          <figcaption className="border-t border-line bg-surface px-4 py-2.5 text-[13px] text-muted">
            AI-generated try-on. Fit, size and colour may differ in real life.
          </figcaption>
        </figure>

        <div>
          <h2 className="font-display text-[24px] text-ink">{look.products.length > 0 ? "Shop this look" : "Try your own look"}</h2>
          {look.products.length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-4 xl:grid-cols-3">
              {look.products.map((p) => (
                <ProductCard
                  key={p.id}
                  image={p.image_url}
                  name={p.name}
                  priceCents={p.price_cents}
                  currency={p.currency}
                  shop={p.shop}
                  primary={{ label: "Try it on yourself", href: `/try?product=${p.id}` }}
                  secondary={{ label: "View in shop ↗", href: p.buy_url, external: true }}
                />
              ))}
            </div>
          )}
          <div className="mt-8 rounded-[24px] border border-sage/40 bg-sage-tint/25 p-6">
            <p className="font-display text-[22px] text-ink">See it on <em>you</em></p>
            <p className="mt-1 text-[15px] text-ink-soft">
              Upload your photo once and try any outfit, shoes or jewellery on yourself before you buy.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Button href="/sign-up" size="md">Create your free account <span aria-hidden="true">→</span></Button>
              <Button href="/" size="md" variant="outline">What is TryOnU?</Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
