import Image from "next/image";
import { CheckIcon } from "@/components/ui/Icons";
import { LensIcon } from "@/components/lens/LensIcon";
import { Kicker, Section } from "@/components/marketing/primitives";
import { Button } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";
import { PHOTOS } from "@/lib/media";

// where the example's items are on the photo (fractions), as Find the look marks them
const SPOTS: { n: number; label: string; x: number; y: number }[] = [
  { n: 1, label: "Pink wool coat", x: 0.52, y: 0.5 },
  { n: 2, label: "Paisley scarf", x: 0.5, y: 0.34 },
  { n: 3, label: "Black tights", x: 0.56, y: 0.8 },
  { n: 4, label: "Ankle boots", x: 0.53, y: 0.95 },
];

/** On the home page: Find the look (search the shops with a photo). */
export function FindLookPromo() {
  return (
    <Section id="find-look" className="border-y border-line bg-paper-2/50">
      <div className="grid items-center gap-10 lg:grid-cols-2">
        <Reveal>
          <Kicker>New · Find the look</Kicker>
          <h2 className="font-display text-[clamp(32px,4.4vw,52px)] leading-[1.02] text-ink">
            Saw an outfit you love? <em>Find it with a photo.</em>
          </h2>
          <p className="mt-5 max-w-lg text-[17px] leading-relaxed text-muted">
            Upload a photo or a screenshot from Instagram, TikTok, a wedding or the street. TryOnU finds every item in it (clothes,
            shoes, bags, jewellery) and shows you the same products, or the closest ones, from real shops. Then try them on yourself.
          </p>
          <ul className="mt-6 space-y-2 text-[15.5px] text-ink-soft">
            <li className="flex items-center gap-2.5"><span className="grid h-5 w-5 place-items-center rounded-full bg-sage text-[11px] font-bold text-white"><CheckIcon size={12} /></span>Every item found and marked on the photo</li>
            <li className="flex items-center gap-2.5"><span className="grid h-5 w-5 place-items-center rounded-full bg-sage text-[11px] font-bold text-white"><CheckIcon size={12} /></span>Exact matches first, then the closest alternatives</li>
            <li className="flex items-center gap-2.5"><span className="grid h-5 w-5 place-items-center rounded-full bg-sage text-[11px] font-bold text-white"><CheckIcon size={12} /></span>Lowest price in one tap, and try the whole look on you</li>
          </ul>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button href="/find-look" size="lg">
              <LensIcon size={20} /> Search with a photo
            </Button>
          </div>
        </Reveal>

        <Reveal delay={120}>
          <div className="mx-auto flex max-w-[520px] items-center gap-4">
            <div className="relative aspect-[3/4] w-[58%] shrink-0 overflow-hidden rounded-[22px] border border-white/70 bg-white shadow-lift">
              <Image src={PHOTOS.lookPinkCoat.src} alt="An outfit photo with each item marked" fill className="object-cover object-top" sizes="(max-width: 1024px) 55vw, 300px" />
              {SPOTS.map((s) => (
                <span
                  key={s.n}
                  aria-hidden="true"
                  className="absolute grid h-7 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white text-[13px] font-bold text-[#1c1b17] shadow-lift ring-2 ring-sage"
                  style={{ left: `${s.x * 100}%`, top: `${s.y * 100}%` }}
                >
                  {s.n}
                </span>
              ))}
            </div>
            <ol className="min-w-0 flex-1 space-y-2">
              {SPOTS.map((s) => (
                <li key={s.n} className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-[14px] text-ink shadow-sm">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-sage text-[12px] font-bold text-white">{s.n}</span>
                  <span className="truncate">{s.label}</span>
                </li>
              ))}
              <li className="px-1 pt-1 text-[13px] text-muted">…each with products from real shops</li>
            </ol>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
