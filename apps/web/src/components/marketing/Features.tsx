import Image from "next/image";
import { Reveal } from "@/components/ui/Reveal";
import { Section, SectionHead } from "./primitives";
import { PHOTOS, type Photo } from "@/lib/media";

type Row = {
  kicker: string;
  title: string;
  body: string;
  photo: Photo;
  pill: string;
};

const ROWS: Row[] = [
  {
    kicker: "Virtual try-on",
    title: "The product, on your body",
    body: "Pick anything from a connected store and our AI renders it on your fitting profile — fabric drape, fit and proportion held true, not a flat paste-on.",
    photo: PHOTOS.lookPinkCoat,
    pill: "Photoreal output",
  },
  {
    kicker: "Consistent you",
    title: "Same face, every look",
    body: "Your identity stays locked across every garment and pose, so you can compare ten options and trust that you're seeing you in each one.",
    photo: PHOTOS.portraitStudio,
    pill: "Identity-locked",
  },
];

const MINI = [
  {
    title: "High-resolution results",
    body: "Zoomable, crisp renders you can actually judge fit from.",
  },
  {
    title: "One reusable profile",
    body: "Upload photos once; every future try-on reuses them.",
  },
  {
    title: "Shop the original",
    body: "Every look links straight to the retailer's real listing.",
  },
];

export function Features() {
  return (
    <Section id="features">
      <SectionHead
        align="center"
        kicker="Everything you need"
        title={
          <>
            Everything you need to <em>shop with confidence</em>
          </>
        }
        sub="No more guessing from a model who isn't you. See the real product on your body before you spend."
      />

      <div className="flex flex-col gap-6">
        {ROWS.map((row, i) => (
          <Reveal
            key={row.title}
            className={`grid items-center gap-8 overflow-hidden rounded-[28px] border border-line bg-surface p-6 md:grid-cols-2 md:p-0 ${
              i % 2 === 1 ? "md:[&>div:first-child]:order-2" : ""
            }`}
          >
            <div className="md:p-12">
              <p className="mb-3 text-[12px] font-semibold uppercase tracking-[0.16em] text-sage">
                {row.kicker}
              </p>
              <h3 className="font-display text-[28px] leading-tight text-ink sm:text-[34px]">
                {row.title}
              </h3>
              <p className="mt-4 max-w-md text-[15px] leading-relaxed text-muted">
                {row.body}
              </p>
              <span className="mt-6 inline-flex rounded-full border border-line-strong px-3.5 py-1.5 text-[12px] font-medium text-ink-soft">
                {row.pill}
              </span>
            </div>
            <div className="relative h-[300px] overflow-hidden rounded-[22px] md:h-[380px] md:rounded-none">
              <Image
                src={row.photo.src}
                alt={row.photo.alt}
                fill
                className="object-cover object-top"
                sizes="(max-width: 768px) 100vw, 560px"
              />
            </div>
          </Reveal>
        ))}
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {MINI.map((m) => (
          <Reveal
            key={m.title}
            className="rounded-[22px] border border-line bg-surface p-6"
          >
            <h4 className="text-[15px] font-semibold text-ink">{m.title}</h4>
            <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
              {m.body}
            </p>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
