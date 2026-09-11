/**
 * Brand placeholder for a model / product image slot.
 *
 * The prototype's other images were screenshots of an older UI (baked-in
 * cards, logos, dark backgrounds), so they can't be reused cleanly. Drop a
 * real asset in by swapping <LookTile> for <Image> — the aspect box and
 * rounding already match.
 */
export function LookTile({
  label,
  className = "",
  variant = "sage",
}: {
  label: string;
  className?: string;
  variant?: "sage" | "paper";
}) {
  const bg =
    variant === "sage"
      ? "linear-gradient(155deg, var(--color-sage-tint-2), var(--color-paper-2) 70%)"
      : "linear-gradient(155deg, var(--color-paper-2), var(--color-sage-tint) 90%)";

  return (
    <div
      className={`relative flex h-full w-full items-center justify-center overflow-hidden ${className}`}
      style={{ background: bg }}
      role="img"
      aria-label={`${label} (placeholder)`}
    >
      <svg
        viewBox="0 0 120 150"
        className="h-[62%] w-auto opacity-[0.28]"
        fill="none"
        aria-hidden="true"
      >
        <rect
          x="8"
          y="8"
          width="104"
          height="134"
          rx="10"
          stroke="var(--color-sage-deep)"
          strokeWidth="2"
        />
        <circle cx="60" cy="52" r="17" fill="var(--color-sage-deep)" />
        <path
          d="M27 128c0-20 14.8-33 33-33s33 13 33 33"
          fill="var(--color-sage-deep)"
        />
      </svg>
      <span className="absolute bottom-3 left-3 rounded-full bg-surface/85 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-soft backdrop-blur">
        {label}
      </span>
      <span className="absolute right-3 top-3 font-display text-[13px] italic text-sage-deep/60">
        TryOnU
      </span>
    </div>
  );
}
