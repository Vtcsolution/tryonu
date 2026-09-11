import type { ReactNode } from "react";
import { Reveal } from "@/components/ui/Reveal";

export function Section({
  id,
  className = "",
  children,
  tight = false,
}: {
  id?: string;
  className?: string;
  children: ReactNode;
  tight?: boolean;
}) {
  return (
    <section id={id} className={`${tight ? "py-16" : "py-24 md:py-28"} ${className}`}>
      <div className="mx-auto w-[min(1180px,calc(100%-42px))]">{children}</div>
    </section>
  );
}

export function Kicker({ children }: { children: ReactNode }) {
  return (
    <p className="mb-3 text-[12px] font-semibold uppercase tracking-[0.16em] text-sage">
      {children}
    </p>
  );
}

export function SectionHead({
  kicker,
  title,
  sub,
  align = "split",
}: {
  kicker: string;
  title: ReactNode;
  sub?: ReactNode;
  align?: "split" | "center";
}) {
  if (align === "center") {
    return (
      <Reveal className="mx-auto mb-12 max-w-2xl text-center">
        <Kicker>{kicker}</Kicker>
        <h2 className="font-display text-[clamp(30px,4.4vw,52px)] leading-[1.04] text-ink">
          {title}
        </h2>
        {sub && (
          <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
            {sub}
          </p>
        )}
      </Reveal>
    );
  }

  return (
    <Reveal className="mb-12 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div>
        <Kicker>{kicker}</Kicker>
        <h2 className="font-display text-[clamp(30px,4.4vw,52px)] leading-[1.04] text-ink">
          {title}
        </h2>
      </div>
      {sub && (
        <p className="max-w-md text-[15px] leading-relaxed text-muted">{sub}</p>
      )}
    </Reveal>
  );
}
