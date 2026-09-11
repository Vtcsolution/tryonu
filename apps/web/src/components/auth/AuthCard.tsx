import type { ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";

export function AuthCard({
  kicker,
  title,
  subtitle,
  children,
  footer,
}: {
  kicker: string;
  title: ReactNode;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-paper px-4 py-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-[-10%] h-[460px] w-[460px] -translate-x-1/2 rounded-full bg-sage-tint/60 blur-[90px]"
      />
      <div className="relative w-full max-w-[420px]">
        <div className="mb-8 flex justify-center">
          <Logo size={30} />
        </div>

        <div className="rounded-[28px] border border-line bg-surface p-8 shadow-lift">
          <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.16em] text-sage">
            {kicker}
          </p>
          <h1 className="font-display text-[28px] leading-tight text-ink">{title}</h1>
          {subtitle && <p className="mt-2 text-[14px] text-muted">{subtitle}</p>}

          <div className="mt-7">{children}</div>
        </div>

        {footer && <div className="mt-6 text-center text-[13px] text-muted">{footer}</div>}
      </div>
    </div>
  );
}
