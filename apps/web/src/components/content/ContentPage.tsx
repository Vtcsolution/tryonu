import type { ReactNode } from "react";
import { SiteChrome } from "@/components/layout/SiteChrome";

/** The frame of an information page (about, pricing, legal…): a calm header, then the content. */
export function ContentPage({
  kicker,
  title,
  intro,
  children,
  narrow = false,
}: {
  kicker: string;
  title: ReactNode;
  intro?: ReactNode;
  children: ReactNode;
  narrow?: boolean;
}) {
  return (
    <SiteChrome>
      <header className={`border-b border-line bg-paper-2/60 ${intro ? "" : "max-lg:hidden"}`}>
        <div className={`mx-auto py-4 lg:py-16 ${narrow ? "w-[min(860px,calc(100%-32px))]" : "tu-container"}`}>
          <p className="text-[13px] font-semibold uppercase tracking-[0.16em] text-sage-deep max-lg:hidden">{kicker}</p>
          <h1 className="mt-2 font-display text-[clamp(32px,5vw,54px)] leading-[1.05] text-ink max-lg:hidden">{title}</h1>
          {intro && <p className="max-w-2xl text-[15.5px] leading-relaxed text-ink-soft lg:mt-4 lg:text-[17.5px]">{intro}</p>}
        </div>
      </header>
      <div className={`mx-auto py-6 lg:py-16 ${narrow ? "w-[min(860px,calc(100%-32px))]" : "tu-container"}`}>
        {children}
      </div>
    </SiteChrome>
  );
}

/** Legal and policy text: numbered sections, readable line length. */
export function LegalBody({ updated, children }: { updated: string; children: ReactNode }) {
  return (
    <div className="legal text-[16px] leading-[1.75] text-ink-soft [&_a]:text-sage-deep [&_a]:underline [&_h2]:mt-10 [&_h2]:font-display [&_h2]:text-[24px] [&_h2]:leading-tight [&_h2]:text-ink [&_li]:mt-1.5 [&_p]:mt-3 [&_strong]:text-ink [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-6">
      <p className="!mt-0 text-[14px] text-muted">Last updated: {updated}</p>
      {children}
    </div>
  );
}

/** A titled card in a grid. */
export function InfoCard({ title, children, footer }: { title: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="flex flex-col rounded-[22px] border border-line bg-surface p-6">
      <h3 className="text-[19px] font-semibold text-ink">{title}</h3>
      <div className="mt-2 flex-1 text-[15.5px] leading-relaxed text-ink-soft">{children}</div>
      {footer && <div className="mt-5">{footer}</div>}
    </div>
  );
}

/** Columns for a row of cards, by how many there are: never an empty column
 * at the end of the row (3 packs fill 3 columns, not 3 of 4). */
export function cardGrid(count: number): string {
  if (count <= 1) return "grid gap-5 sm:max-w-md";
  if (count === 2) return "grid gap-5 sm:grid-cols-2";
  if (count === 3) return "grid gap-5 md:grid-cols-3";
  if (count === 4) return "grid gap-5 sm:grid-cols-2 xl:grid-cols-4";
  return "grid gap-5 sm:grid-cols-2 lg:grid-cols-3";
}

/** Numbered steps. */
export function Steps({ steps }: { steps: { title: string; text: ReactNode }[] }) {
  return (
    <ol className="grid gap-4 md:grid-cols-3">
      {steps.map((s, i) => (
        <li key={s.title} className="rounded-[22px] border border-line bg-surface p-6">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-sage text-[15px] font-semibold text-white">{i + 1}</span>
          <p className="mt-3 text-[18px] font-semibold text-ink">{s.title}</p>
          <p className="mt-1 text-[15.5px] leading-relaxed text-ink-soft">{s.text}</p>
        </li>
      ))}
    </ol>
  );
}

export function SectionTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-6">
      <h2 className="font-display text-[clamp(26px,3.4vw,36px)] leading-tight text-ink">{children}</h2>
      {sub && <p className="mt-2 max-w-2xl text-[16px] text-muted">{sub}</p>}
    </div>
  );
}
