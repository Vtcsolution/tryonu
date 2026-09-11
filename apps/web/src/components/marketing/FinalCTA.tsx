import Image from "next/image";
import { Reveal } from "@/components/ui/Reveal";
import { Button } from "@/components/ui/Button";
import { PHOTOS } from "@/lib/media";

export function FinalCTA() {
  return (
    <section className="py-20 md:py-28">
      <div className="mx-auto w-[min(1180px,calc(100%-42px))]">
        <Reveal className="relative overflow-hidden rounded-[32px] bg-sage px-8 py-16 text-center text-white sm:px-12 md:py-20">
          {/* photo bleeds in from the right, faded into the sage */}
          <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-[46%] md:block">
            <Image
              src={PHOTOS.shoppingBags.src}
              alt=""
              fill
              className="object-cover object-center opacity-25 mix-blend-luminosity"
              sizes="540px"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-sage via-sage/70 to-transparent" />
          </div>

          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 -bottom-40 mx-auto h-[420px] w-[820px] rounded-full bg-white/10 blur-3xl"
          />
          <p className="relative text-[12px] font-semibold uppercase tracking-[0.18em] text-white/75">
            Fashion meets technology
          </p>
          <h2 className="relative mx-auto mt-4 max-w-2xl font-display text-[clamp(30px,4.6vw,52px)] leading-[1.05]">
            Ready to try it <em>before you buy it?</em>
          </h2>
          <p className="relative mx-auto mt-4 max-w-md text-[15px] text-white/80">
            Build your fitting profile once. Use it on every product, from every
            store, every time.
          </p>
          <div className="relative mt-8 flex justify-center">
            <Button href="/try" variant="light" size="lg">
              Create my fitting profile <span aria-hidden="true">→</span>
            </Button>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
