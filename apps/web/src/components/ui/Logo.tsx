import Link from "next/link";

type LogoProps = {
  /** Height of the mark + wordmark in px. */
  size?: number;
  /** Render just the mark, no wordmark. */
  markOnly?: boolean;
  /** Invert for use on dark / sage backgrounds. */
  tone?: "ink" | "light";
  href?: string;
  className?: string;
};

/**
 * TryOnU wordmark — minimal rounded-square mark ("you" in a frame:
 * a soft U cradling a head-dot) + a tight, low-tracking wordmark.
 * Used identically in navbar, footer, auth and dashboard.
 */
export function Logo({
  size = 30,
  markOnly = false,
  tone = "ink",
  href = "/",
  className = "",
}: LogoProps) {
  const markFill = tone === "light" ? "#ffffff" : "var(--color-sage-ink)";
  const glyph = tone === "light" ? "var(--color-sage-ink)" : "#ffffff";
  const word = tone === "light" ? "#ffffff" : "var(--color-ink)";

  const mark = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect width="32" height="32" rx="9" fill={markFill} />
      <path
        d="M9 9v7.2A7 7 0 0 0 23 16.2V9"
        stroke={glyph}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="16" cy="10.5" r="2.6" fill={glyph} />
    </svg>
  );

  const content = (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      {mark}
      {!markOnly && (
        <span
          className="font-semibold tracking-[-0.03em]"
          style={{ color: word, fontSize: size * 0.62 }}
        >
          Try<span style={{ color: "var(--color-sage)" }}>On</span>U
        </span>
      )}
    </span>
  );

  if (!href) return content;

  return (
    <Link href={href} aria-label="TryOnU — home" className="inline-flex">
      {content}
    </Link>
  );
}
