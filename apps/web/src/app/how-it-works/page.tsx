import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { Reveal } from "@/components/ui/Reveal";
import { Button } from "@/components/ui/Button";
import { Section, Kicker } from "@/components/marketing/primitives";
import { Pipeline } from "@/components/marketing/Pipeline";
import { PHOTOS, type Photo } from "@/lib/media";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "From your photo to your cart: how TryOnU turns 7–10 photos into a reusable fitting profile and renders real retailer products on you with AI.",
};

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
    title: "Build your fitting profile",
    body: "Upload 7–10 clear photos — front, sides, 45° and full body. TryOnU turns them into one reusable fitting profile, so you never do this again.",
    meta: "~2 minutes · one time",
    photo: PHOTOS.portraitWinter,
  },
  {
    n: "02",
    title: "Choose any product",
    body: "Browse products pulled from Amazon, eBay, Flipkart and Daraz, or paste a link. We normalise the listing — image, price, sizes — into a clean product card.",
    meta: "Any connected retailer",
    photo: PHOTOS.clothingRail,
  },
  {
    n: "03",
    title: "AI renders it on you",
    body: "The try-on runs as a background job: credits are reserved, the request is queued, an AI worker generates the look, and the result is stored privately. You watch the status update live.",
    meta: "queued → processing → completed · ~10–30s",
    photo: PHOTOS.lookBlueCoat,
  },
  {
    n: "04",
    title: "Compare, then shop the original",
    body: "Line looks up side by side, keep the ones you love, and click straight through to buy from the original retailer. TryOnU never sits between you and checkout.",
    meta: "Shop Now → original listing",
    photo: PHOTOS.shoppingBags,
  },
];

export default function HowItWorksPage() {
  return (
    <SiteChrome>
      {/* hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-[-15%] -z-10 h-[460px] w-[460px] -translate-x-1/2 rounded-full bg-sage-tint/60 blur-[90px]"
        />
        <div className="mx-auto w-[min(1180px,calc(100%-42px))] py-16 text-center md:py-24">
          <Reveal>
            <Kicker>How it works</Kicker>
            <h1 className="mx-auto max-w-3xl font-display text-[clamp(38px,6vw,68px)] leading-[1.02] text-ink">
              From your photo to <em>your cart</em>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-[17px] leading-relaxed text-muted">
              One fitting profile. Every store. Real products, rendered on you by
              AI, in about half a minute.
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
                    <span className="absolute left-4 top-4 rounded-full bg-surface/90 px-2.5 py-1 font-display text-[13px] text-ink backdrop-blur">
                      {s.n}
                    </span>
                  </Reveal>

                  <Reveal
                    variant={flip ? "right" : "left"}
                    delay={100}
                    className={flip ? "md:order-1 md:text-right" : ""}
                  >
                    <p className="font-display text-[15px] text-sage">
                      Step {s.n}
                    </p>
                    <h2 className="mt-2 font-display text-[clamp(26px,3.6vw,40px)] leading-tight text-ink">
                      {s.title}
                    </h2>
                    <p className="mt-4 max-w-md text-[15px] leading-relaxed text-muted md:inline-block">
                      {s.body}
                    </p>
                    <p
                      className={`mt-4 flex items-center gap-2 text-[12.5px] text-faint ${
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
          <p className="mt-4 text-[15px] leading-relaxed text-muted">
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
              <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
                {c.b}
              </p>
            </Reveal>
          ))}
        </div>
      </Section>

      {/* cta */}
      <section className="pb-24">
        <div className="mx-auto w-[min(1180px,calc(100%-42px))]">
          <Reveal className="rounded-[32px] bg-sage px-8 py-14 text-center text-white md:py-16">
            <h2 className="mx-auto max-w-xl font-display text-[clamp(26px,4vw,42px)] leading-tight">
              See your first look in <em>under a minute</em>
            </h2>
            <div className="mt-7 flex justify-center">
              <Button href="/try" variant="light" size="lg">
                Start now <span aria-hidden="true">→</span>
              </Button>
            </div>
            <p className="mt-4 text-[12px] text-white/70">
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
