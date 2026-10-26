import Image from "next/image";
import { ShowcaseSection } from "@/components/marketing/ShowcaseLooks";
import Link from "next/link";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { Reveal } from "@/components/ui/Reveal";
import { Button } from "@/components/ui/Button";
import { Section, Kicker } from "@/components/marketing/primitives";
import { Pipeline } from "@/components/marketing/Pipeline";
import { PHOTOS, type Photo } from "@/lib/media";
import { SITE_DEFINITION, pageMeta } from "@/lib/seo";
import { JsonLd } from "@/components/seo/JsonLd";

export const metadata = pageMeta({
  title: "How Virtual Try-On Works: From Your Photo to Your Cart",
  description:
    "How TryOnU works: add one photo, pick real products or ask the AI Stylist, see yourself wearing them in under a minute, then buy from the original store.",
  path: "/how-it-works",
  keywords: ["how virtual try on works", "how to try clothes online"],
});

type Step = {
  n: string;
  title: string;
  body: string;
  meta: string;
  photo: Photo;
};

const STEPS: Step[] = [
  {
    n: "01",
    title: "Add one photo of yourself",
    body: "A clear photo of you standing, facing the front. You do this only once, and only you can see it. A side or back photo is optional.",
    meta: "About 1 minute · one time",
    photo: PHOTOS.portraitWinter,
  },
  {
    n: "02",
    title: "Say what you want",
    body: "Tap a ready look like \"Pink bridal look\", type what you want in your own words, or upload a photo of an outfit you like. TryOnU then searches real shops for you right away: local shops on TryOnU that deliver to you first, then eBay, AliExpress and brand stores.",
    meta: "Real products, real shops",
    photo: PHOTOS.clothingRail,
  },
  {
    n: "03",
    title: "See it on you",
    body: "Press Try it on. In about a minute the AI shows you wearing the products, a single piece or a whole outfit. You can leave the page; your look waits for you. If a try-on fails, your credits come back.",
    meta: "About 1 minute",
    photo: PHOTOS.lookBlueCoat,
  },
  {
    n: "04",
    title: "Buy from the shop",
    body: "Like it? Tap Shop now next to each product to buy it from the shop itself, at its normal price. TryOnU does not sell anything itself. Save the look or share it with friends.",
    meta: "Shop now → the shop's own page",
    photo: PHOTOS.shoppingBags,
  },
];

export default function HowItWorksPage() {
  const howTo = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: "How to try clothes on your own photo with TryOnU",
    description: SITE_DEFINITION,
    totalTime: "PT3M",
    step: STEPS.map((s, i) => ({ "@type": "HowToStep", position: i + 1, name: s.title, text: s.body })),
  };
  return (
    <SiteChrome>
      <JsonLd data={howTo} />
      {/* hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-[-15%] -z-10 h-[460px] w-[460px] -translate-x-1/2 rounded-full bg-sage-tint/60 blur-[90px]"
        />
        <div className="tu-container py-16 text-center md:py-24">
          <Reveal>
            <Kicker>How it works</Kicker>
            <h1 className="mx-auto max-w-3xl font-display text-[clamp(38px,6vw,68px)] leading-[1.02] text-ink">
              From your photo to <em>your cart</em>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-[17px] leading-relaxed text-muted">
              Add your photo, say what you want, and see real products from real shops on you in about a
              minute. Then buy from the shop itself.
            </p>
            <div className="mt-8 flex justify-center">
              <Button href="/try" size="lg">
                Try it now <span aria-hidden="true">→</span>
              </Button>
            </div>
          </Reveal>
        </div>
      </section>

      {/* the flow */}
      <Section tight>
        <div className="relative">
          {/* animated spine (desktop) */}
          <div
            aria-hidden="true"
            className="absolute left-1/2 top-0 hidden h-full w-px -translate-x-1/2 bg-line md:block"
          />

          <div className="flex flex-col gap-16 md:gap-24">
            {STEPS.map((s, i) => {
              const flip = i % 2 === 1;
              return (
                <div
                  key={s.n}
                  className="relative grid items-center gap-8 md:grid-cols-2 md:gap-14"
                >
                  {/* node on the spine */}
                  <div
                    aria-hidden="true"
                    className="absolute left-1/2 top-1/2 hidden h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sage ring-4 ring-paper md:block"
                  />

                  <Reveal
                    variant={flip ? "left" : "right"}
                    className={`relative aspect-[4/3] overflow-hidden rounded-[26px] border border-line shadow-lift ${
                      flip ? "md:order-2" : ""
                    }`}
                  >
                    <Image
                      src={s.photo.src}
                      alt={s.photo.alt}
                      fill
                      className="object-cover object-top"
                      sizes="(max-width: 768px) 100vw, 520px"
                    />
                    <span className="absolute left-4 top-4 rounded-full bg-surface/90 px-2.5 py-1 font-display text-[14px] text-ink backdrop-blur">
                      {s.n}
                    </span>
                  </Reveal>

                  <Reveal
                    variant={flip ? "right" : "left"}
                    delay={100}
                    className={flip ? "md:order-1 md:text-right" : ""}
                  >
                    <p className="font-display text-[16px] text-sage">
                      Step {s.n}
                    </p>
                    <h2 className="mt-2 font-display text-[clamp(26px,3.6vw,40px)] leading-tight text-ink">
                      {s.title}
                    </h2>
                    <p className="mt-4 max-w-md text-[16px] leading-relaxed text-muted md:inline-block">
                      {s.body}
                    </p>
                    <p
                      className={`mt-4 flex items-center gap-2 text-[13.5px] text-faint ${
                        flip ? "md:justify-end" : ""
                      }`}
                    >
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-sage" />
                      {s.meta}
                    </p>
                  </Reveal>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      {/* behind the scenes */}
      <Section id="pipeline" className="bg-paper-2">
        <Reveal className="mb-10 max-w-2xl">
          <Kicker>Behind the scenes</Kicker>
          <h2 className="font-display text-[clamp(28px,4vw,46px)] leading-tight text-ink">
            A real job pipeline, <em>not a spinner</em>
          </h2>
          <p className="mt-4 text-[16px] leading-relaxed text-muted">
            Long AI renders never block your browser. Every try-on is a tracked
            job with reserved credits and a safe refund if it fails.
          </p>
        </Reveal>
        <Reveal variant="scale">
          <Pipeline />
        </Reveal>
      </Section>

      {/* accuracy cards */}
      <Section>
        <Reveal className="mb-10">
          <Kicker>Why it looks right</Kicker>
          <h2 className="font-display text-[clamp(28px,4vw,46px)] leading-tight text-ink">
            Built for <em>trustworthy</em> fit
          </h2>
        </Reveal>
        <div className="grid gap-5 md:grid-cols-3">
          {[
            {
              t: "Identity-locked",
              b: "Your face and body stay consistent across every garment and pose.",
            },
            {
              t: "True drape & fit",
              b: "Fabric falls and stretches the way it would in person — not a flat overlay.",
            },
            {
              t: "High-resolution",
              b: "Zoomable output you can actually judge seams, length and proportion from.",
            },
          ].map((c, i) => (
            <Reveal
              key={c.t}
              variant="up"
              delay={i * 90}
              className="rounded-[22px] border border-line bg-surface p-6"
            >
              <h3 className="font-display text-[19px] text-ink">{c.t}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-muted">
                {c.b}
              </p>
            </Reveal>
          ))}
        </div>
      </Section>

      <div className="tu-container pb-20">
        <ShowcaseSection look="men" />
      </div>

      {/* cta */}
      <section className="pb-24">
        <div className="tu-container">
          <Reveal className="rounded-[32px] bg-sage px-8 py-14 text-center text-white md:py-16">
            <h2 className="mx-auto max-w-xl font-display text-[clamp(26px,4vw,42px)] leading-tight">
              See your first look in <em>under a minute</em>
            </h2>
            <div className="mt-7 flex justify-center">
              <Button href="/try" variant="light" size="lg">
                Start now <span aria-hidden="true">→</span>
              </Button>
            </div>
            <p className="mt-4 text-[13px] text-white/70">
              No credit card required ·{" "}
              <Link href="/" className="underline">
                back to home
              </Link>
            </p>
          </Reveal>
        </div>
      </section>
    </SiteChrome>
  );
}
