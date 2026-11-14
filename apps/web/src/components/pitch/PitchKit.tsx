import Link from "next/link";
import type { ReactNode } from "react";
import { CompareSlider, type LookId } from "@/components/marketing/CompareSlider";
import { Reveal } from "@/components/ui/Reveal";
import type { ReadyLook } from "@/lib/api/endpoints";
import { lookPath } from "@/lib/lookSlug";

/**
 * Building blocks for the three pitch pages sent by DM (/invest, /grow,
 * /try-on-api): a big hero, an animated 3-step flow, the real before/after,
 * a moving strip of real looks, tiles and a strong call to action.
 * Few words, large type, real TryOnU pictures.
 */

export const CONTACT_EMAIL = "hello@tryonu.app";

export function mailto(subject: string) {
  return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}`;
}

export function PitchHero({
  kicker,
  title,
  sub,
  primary,
  secondary,
  look = "women",
}: {
  kicker: string;
  title: ReactNode;
  sub: string;
  primary: { label: string; href: string };
  secondary?: { label: string; href: string };
  look?: LookId;
}) {
  return (
    <section className="relative overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute -right-32 -top-32 h-[520px] w-[520px] rounded-full bg-sage/25 blur-[120px]" />
      <div className="relative mx-auto grid w-[min(1200px,calc(100%-32px))] items-center gap-10 py-12 md:py-20 lg:grid-cols-[1.05fr_1fr]">
        <Reveal>
          <p className="inline-flex rounded-full bg-sage-tint px-3.5 py-1.5 text-[13px] font-bold uppercase tracking-[0.14em] text-sage-deep">{kicker}</p>
          <h1 className="mt-4 font-display text-[clamp(38px,6vw,68px)] leading-[1.02] text-ink">{title}</h1>
          <p className="mt-5 max-w-xl text-[19px] leading-relaxed text-ink-soft">{sub}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <BigButton href={primary.href}>{primary.label}</BigButton>
            {secondary && (
              <BigButton href={secondary.href} outline>
                {secondary.label}
              </BigButton>
            )}
          </div>
        </Reveal>
        <Reveal variant="scale" delay={150}>
          <div className="mx-auto max-w-[460px]">
            <CompareSlider look={look} compact />
            <p className="mt-3 text-center text-[14px] font-semibold text-muted">Drag the line: before and after a real TryOnU try-on</p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export function BigButton({ href, children, outline = false }: { href: string; children: ReactNode; outline?: boolean }) {
  const external = href.startsWith("mailto:") || href.startsWith("http");
  const cls = `tu-press inline-flex min-h-[56px] items-center gap-2 rounded-full px-7 text-[17px] font-bold transition-colors ${
    outline ? "border-2 border-ink/20 text-ink hover:border-sage" : "tu-attention bg-sage text-white shadow-lift hover:bg-sage-deep"
  }`;
  return external ? (
    <a href={href} className={cls}>
      {children} <span aria-hidden="true">→</span>
    </a>
  ) : (
    <Link href={href} className={cls}>
      {children} <span aria-hidden="true">→</span>
    </Link>
  );
}

export function PitchSection({ kicker, title, children, tint = false }: { kicker?: string; title: ReactNode; children: ReactNode; tint?: boolean }) {
  return (
    <section className={tint ? "bg-paper-2" : ""}>
      <div className="mx-auto w-[min(1200px,calc(100%-32px))] py-14 md:py-20">
        <Reveal>
          {kicker && <p className="text-[13px] font-bold uppercase tracking-[0.14em] text-sage-deep">{kicker}</p>}
          <h2 className="mt-2 max-w-3xl font-display text-[clamp(30px,4.4vw,48px)] leading-[1.06] text-ink">{title}</h2>
        </Reveal>
        <div className="mt-9">{children}</div>
      </div>
    </section>
  );
}

/** Three big steps with numbers, joined by a line that draws in. */
export function StepFlow({ steps }: { steps: { title: string; text: string; icon: ReactNode }[] }) {
  return (
    <ol className="relative grid gap-6 md:grid-cols-3">
      <span aria-hidden="true" className="absolute left-[16%] right-[16%] top-9 hidden h-[3px] origin-left animate-[tu-line-grow_1.4s_ease_both] rounded-full bg-sage/40 md:block" />
      {steps.map((s, i) => (
        <Reveal as="li" key={s.title} delay={i * 160} className="relative flex flex-col items-center text-center">
          <span className="relative grid h-[72px] w-[72px] place-items-center rounded-full bg-sage text-white shadow-lift ring-8 ring-paper">
            {s.icon}
            <span className="absolute -right-1 -top-1 grid h-7 w-7 place-items-center rounded-full bg-ink text-[13px] font-bold text-paper">{i + 1}</span>
          </span>
          <p className="mt-4 font-display text-[24px] text-ink">{s.title}</p>
          <p className="mt-1 max-w-[300px] text-[16.5px] leading-relaxed text-ink-soft">{s.text}</p>
        </Reveal>
      ))}
    </ol>
  );
}

/** Big tiles: one bold line and a short sentence each. */
export function Tiles({ items, columns = 3 }: { items: { big: string; text: string }[]; columns?: 2 | 3 | 4 }) {
  const cols = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-2 lg:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4" }[columns];
  return (
    <div className={`grid gap-4 ${cols}`}>
      {items.map((t, i) => (
        <Reveal key={t.big} delay={i * 90} className="rounded-[24px] border border-line bg-surface p-6 transition-shadow hover:shadow-lift">
          <p className="font-display text-[28px] leading-tight text-ink">{t.big}</p>
          <p className="mt-2 text-[16px] leading-relaxed text-ink-soft">{t.text}</p>
        </Reveal>
      ))}
    </div>
  );
}

/** Real ready looks moving sideways, endlessly. */
export function LooksMarquee({ looks }: { looks: ReadyLook[] }) {
  if (looks.length < 3) return null;
  const row = [...looks, ...looks];
  return (
    <div className="relative overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_8%,black_92%,transparent)]">
      <ul className="flex w-max gap-4 [animation:tu-marquee_60s_linear_infinite] hover:[animation-play-state:paused]">
        {row.map((l, i) => (
          <li key={`${l.id}-${i}`} className="w-[220px] shrink-0">
            <Link href={lookPath(l)} className="block overflow-hidden rounded-[20px] border border-line bg-surface">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={l.card_small_url} alt={l.title} loading="lazy" className="aspect-[4/5] w-full object-cover" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CtaBand({ title, sub, primary, secondary }: { title: string; sub: string; primary: { label: string; href: string }; secondary?: { label: string; href: string } }) {
  return (
    <section className="mx-auto w-[min(1200px,calc(100%-32px))] pb-20">
      <Reveal variant="scale" className="relative overflow-hidden rounded-[32px] bg-sage px-7 py-14 text-center text-white md:px-14 md:py-20">
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 -bottom-40 mx-auto h-[380px] w-[760px] max-w-full rounded-full bg-white/10 blur-3xl" />
        <h2 className="relative font-display text-[clamp(30px,4.6vw,50px)] leading-[1.06]">{title}</h2>
        <p className="relative mx-auto mt-4 max-w-2xl text-[18px] leading-relaxed text-white/90">{sub}</p>
        <div className="relative mt-8 flex flex-wrap justify-center gap-3">
          <a
            href={primary.href}
            className="tu-press tu-attention inline-flex min-h-[56px] items-center gap-2 rounded-full bg-white px-8 text-[17px] font-bold text-[#1c1b17] hover:bg-white/90"
          >
            {primary.label} <span aria-hidden="true">→</span>
          </a>
          {secondary && (
            <a href={secondary.href} className="tu-press inline-flex min-h-[56px] items-center gap-2 rounded-full border-2 border-white/60 px-8 text-[17px] font-bold text-white hover:border-white">
              {secondary.label} <span aria-hidden="true">→</span>
            </a>
          )}
        </div>
        <p className="relative mt-5 text-[15px] text-white/85">
          Or write to <b>{CONTACT_EMAIL}</b>
        </p>
      </Reveal>
    </section>
  );
}

/** Simple line icons for the steps. */
export const Icon = {
  photo: (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 7h3l2-3h6l2 3h3v13H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  ),
  hanger: (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 7a2 2 0 1 1 2-2M12 7v2L3 16h18l-9-7" />
    </svg>
  ),
  spark: (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
    </svg>
  ),
  bag: (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 8h14l-1 12H6zM9 8V6a3 3 0 0 1 6 0v2" />
    </svg>
  ),
  store: (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 9l2-5h14l2 5M4 9v11h16V9M3 9h18M9 20v-6h6v6" />
    </svg>
  ),
  code: (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" />
    </svg>
  ),
  chat: (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 5h16v11H9l-5 4z" />
    </svg>
  ),
};
