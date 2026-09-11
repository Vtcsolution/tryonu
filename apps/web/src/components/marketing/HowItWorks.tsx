import Image from "next/image";
import { Reveal } from "@/components/ui/Reveal";
import { Section, SectionHead } from "./primitives";
import { PHOTOS, type Photo } from "@/lib/media";

type Step = {
  n: number;
  title: string;
  body: string;
  photo: Photo;
};

const STEPS: Step[] = [
  {
    n: 1,
    title: "Upload 7–10 photos",
    body: "Front, side, 45° and full-body shots become one reusable fitting profile.",
    photo: PHOTOS.portraitWinter,
  },
  {
    n: 2,
    title: "Pick a product",
    body: "Browse connected retailers or paste a product link. TryOnU normalises it and queues the try-on.",
    photo: PHOTOS.clothingRail,
  },
  {
    n: 3,
    title: "See it & shop it",
    body: "Compare looks side by side, then click through to buy from the original store.",
    photo: PHOTOS.lookYellowSet,
  },
];

export function HowItWorks() {
  return (
    <Section id="how" className="bg-paper-2">
      <SectionHead
        kicker="How it works"
        title={
          <>
            Three steps. <em>That&rsquo;s it.</em>
          </>
        }
        sub="Your photos become one reusable fitting profile. Pick products, compare looks, then buy from the original marketplace."
      />

      <div className="grid gap-5 md:grid-cols-3">
        {STEPS.map((s, i) => (
          <Reveal
            key={s.n}
            delay={i * 90}
            className="flex flex-col overflow-hidden rounded-[24px] border border-line bg-surface"
          >
            <div className="flex items-center gap-3 px-5 pt-5 text-[14px] font-semibold text-ink">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-sage text-white">
                {s.n}
              </span>
              {s.title}
            </div>
            <div className="relative m-5 h-[210px] overflow-hidden rounded-[16px] border border-line">
              <Image
                src={s.photo.src}
                alt={s.photo.alt}
                fill
                className="object-cover object-top"
                sizes="(max-width: 768px) 100vw, 360px"
              />
            </div>
            <p className="px-5 pb-6 text-[13.5px] leading-relaxed text-muted">
              {s.body}
            </p>
          </Reveal>
        ))}
      </div>

      <Reveal className="mt-10 flex justify-center">
        <a
          href="/how-it-works"
          className="group inline-flex items-center gap-2 font-display text-[15px] text-sage transition-colors hover:text-sage-deep"
        >
          See the full flow
          <span
            aria-hidden="true"
            className="transition-transform duration-300 group-hover:translate-x-1"
          >
            →
          </span>
        </a>
      </Reveal>
    </Section>
  );
}
