import Image from "next/image";
import { Reveal } from "@/components/ui/Reveal";
import { Button } from "@/components/ui/Button";
import { RetailerMark } from "./RetailerMark";
import { PHOTOS } from "@/lib/media";

const TICKS = ["Realistic results", "One reusable profile", "Shop the original"];

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* soft warm glow, à la the reference */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-[-10%] -z-10 h-[520px] w-[520px] -translate-x-1/3 rounded-full bg-sage-tint/60 blur-[90px]"
      />

      <div className="mx-auto grid w-[min(1180px,calc(100%-42px))] items-center gap-12 py-16 md:grid-cols-[1.05fr_.9fr] md:py-24 lg:gap-16">
        <Reveal className="max-w-xl">
          <p className="mb-5 text-[12px] font-semibold uppercase tracking-[0.18em] text-sage">
            Try It. See You. Shop It.
          </p>
          <h1 className="font-display text-[clamp(44px,6.4vw,76px)] leading-[0.98] text-ink">
            Try real fashion <em>on&nbsp;you</em>
            <br />
            before you buy.
          </h1>
          <p className="mt-6 max-w-lg text-[17px] leading-relaxed text-muted">
            Upload your photos once. TryOnU places real products from top
            retailers onto your body with AI — then you shop the original
            listing in a click.
          </p>

          <div className="mt-7 flex flex-wrap items-center gap-2.5">
            {(["Amazon", "eBay", "Flipkart", "Daraz"] as const).map((r) => (
              <span
                key={r}
                className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface/70 px-3 py-2 text-[13px] text-ink-soft"
              >
                <RetailerMark name={r} className="text-[13px]" />
              </span>
            ))}
            <span className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface/70 px-3 py-2 text-[13px] text-muted">
              ↗ Affiliate powered
            </span>
          </div>

          <ul className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-ink-soft">
            {TICKS.map((t) => (
              <li key={t} className="flex items-center gap-2">
                <span className="grid h-4 w-4 place-items-center rounded-full bg-sage text-[10px] font-bold text-white">
                  ✓
                </span>
                {t}
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={120} className="relative md:min-h-[500px]">
          {/* floating look cards — free-floating on desktop, a tidy row on mobile */}
          <div className="mb-5 flex gap-4 md:mb-0 md:block">
            <div className="tu-float relative aspect-[4/5] w-1/2 rotate-[-3deg] overflow-hidden rounded-[22px] border border-white/70 bg-white shadow-lift [animation:tu-float_6s_ease-in-out_infinite] md:absolute md:-left-2 md:top-2 md:w-[42%] md:max-w-[190px]">
              <Image
                src={PHOTOS.portraitStudio.src}
                alt={PHOTOS.portraitStudio.alt}
                fill
                className="object-cover object-top"
                sizes="(max-width: 768px) 45vw, 190px"
              />
              <span className="absolute left-2 top-2 rounded-full bg-white/85 px-2.5 py-1 text-[10px] font-semibold text-[#1c1b17] backdrop-blur">
                Your photo
              </span>
            </div>

            <div className="tu-float relative aspect-[4/5] w-1/2 rotate-[2deg] overflow-hidden rounded-[22px] border border-white/70 bg-white shadow-lift [animation:tu-float_7s_ease-in-out_infinite_0.6s] md:absolute md:-right-2 md:top-10 md:w-[46%] md:max-w-[210px]">
              <Image
                src={PHOTOS.lookPinkCoat.src}
                alt={PHOTOS.lookPinkCoat.alt}
                fill
                className="object-cover object-top"
                sizes="(max-width: 768px) 45vw, 210px"
              />
              <span className="absolute left-2 top-2 rounded-full bg-sage px-2.5 py-1 text-[10px] font-semibold text-white">
                Try-on result
              </span>
            </div>
          </div>

          {/* upload card (from the prototype, restyled light) */}
          <div className="relative mx-auto w-full max-w-[370px] rounded-[26px] border border-line bg-surface p-5 shadow-lift md:ml-auto md:mr-0 md:mt-[210px]">
            <div className="rounded-[20px] border border-dashed border-line-strong bg-paper-2/70 px-6 py-8 text-center">
              <div className="mx-auto mb-4 grid h-[52px] w-[52px] place-items-center rounded-[17px] border border-line-strong text-2xl text-sage">
                ⇧
              </div>
              <h3 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">
                Create your fitting profile
              </h3>
              <p className="mt-1.5 text-[13px] text-muted">
                Upload 7–10 clear photos once.
              </p>
              <Button href="/try" size="md" className="mt-4 w-full">
                Create my fitting profile <span aria-hidden="true">→</span>
              </Button>
            </div>
            <div className="my-3.5 flex items-center gap-3 text-[12px] text-faint">
              <span className="h-px flex-1 bg-line" />
              or
              <span className="h-px flex-1 bg-line" />
            </div>
            <a
              href="#studio"
              className="block text-center text-[13px] font-semibold text-sage hover:text-sage-deep"
            >
              try a demo look
            </a>
            <p className="mt-2.5 text-center text-[11px] text-faint">
              No credit card required
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
