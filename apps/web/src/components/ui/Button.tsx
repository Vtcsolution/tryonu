import Link from "next/link";
import type { MouseEventHandler, ReactNode } from "react";

type Variant = "primary" | "outline" | "ghost" | "light";
type Size = "sm" | "md" | "lg";

const base =
  "group inline-flex items-center justify-center gap-2 rounded-full font-medium transform-gpu transition-[transform,background-color,border-color,color] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage/50 focus-visible:ring-offset-2 focus-visible:ring-offset-paper disabled:opacity-50 disabled:pointer-events-none hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] [&>span:last-child]:transition-transform [&>span:last-child]:duration-300 hover:[&>span:last-child]:translate-x-0.5";

const variants: Record<Variant, string> = {
  primary:
    "bg-sage text-white shadow-[0_12px_32px_-14px_rgba(87,99,79,0.55)] hover:bg-sage-deep",
  outline:
    "border border-line-strong text-ink bg-surface/70 hover:bg-surface hover:border-ink/30",
  ghost: "text-ink hover:bg-ink/[0.06]",
  light: "bg-white text-[#1c1b17] shadow-soft hover:bg-neutral-100",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-[13px]",
  md: "h-11 px-5 text-sm",
  lg: "h-[52px] px-7 text-[15px]",
};

export type ButtonProps = {
  variant?: Variant;
  size?: Size;
  className?: string;
  children?: ReactNode;
  href?: string;
  onClick?: MouseEventHandler<HTMLButtonElement | HTMLAnchorElement>;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  "aria-label"?: string;
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  href,
  onClick,
  type = "button",
  disabled,
  ...aria
}: ButtonProps) {
  const cls = `${base} ${variants[variant]} ${sizes[size]} ${className}`;

  if (href) {
    if (href.startsWith("http")) {
      return (
        <a
          href={href}
          className={cls}
          target="_blank"
          rel="noopener noreferrer"
          onClick={onClick}
          {...aria}
        >
          {children}
        </a>
      );
    }
    return (
      <Link href={href} className={cls} onClick={onClick} {...aria}>
        {children}
      </Link>
    );
  }

  return (
    <button
      className={cls}
      type={type}
      disabled={disabled}
      onClick={onClick}
      {...aria}
    >
      {children}
    </button>
  );
}
