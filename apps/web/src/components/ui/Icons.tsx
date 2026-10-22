/** Small line icons used across the site instead of emoji (one style everywhere: 2px strokes, round caps). */

type Props = { size?: number; className?: string };

function Svg({ size = 16, className = "", children }: Props & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`inline-block shrink-0 ${className}`}
    >
      {children}
    </svg>
  );
}

export function CheckIcon(p: Props) {
  return (
    <Svg {...p}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </Svg>
  );
}

export function XIcon(p: Props) {
  return (
    <Svg {...p}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  );
}

export function AlertIcon(p: Props) {
  return (
    <Svg {...p}>
      <path d="M12 3.5 2.5 20h19L12 3.5z" />
      <path d="M12 10v4.5M12 17.5h.01" />
    </Svg>
  );
}

export function StarIcon({ filled = true, ...p }: Props & { filled?: boolean }) {
  return (
    <svg width={p.size ?? 16} height={p.size ?? 16} viewBox="0 0 24 24" aria-hidden="true" className={`inline-block shrink-0 ${p.className ?? ""}`}>
      <path
        d="M12 3.2l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function LockIcon(p: Props) {
  return (
    <Svg {...p}>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </Svg>
  );
}

export function CompassIcon(p: Props) {
  return (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5z" />
    </Svg>
  );
}

export function StoreIcon(p: Props) {
  return (
    <Svg {...p}>
      <path d="M4 9.5 5.5 4h13L20 9.5" />
      <path d="M4 9.5h16v1a3 3 0 0 1-5.3 1.9A3 3 0 0 1 12 13.5a3 3 0 0 1-2.7-1.1A3 3 0 0 1 4 10.5z" />
      <path d="M5.5 13.5V20h13v-6.5" />
    </Svg>
  );
}

export function GlobeIcon(p: Props) {
  return (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </Svg>
  );
}

export function LayersIcon(p: Props) {
  return (
    <Svg {...p}>
      <path d="m12 3 9 5-9 5-9-5z" />
      <path d="m3 13 9 5 9-5" />
    </Svg>
  );
}

/** A round radio mark for big choice buttons. */
export function RadioMark({ on, className = "" }: { on: boolean; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`mr-1.5 inline-grid h-4 w-4 shrink-0 place-items-center rounded-full border-2 align-[-2px] ${
        on ? "border-sage" : "border-line-strong"
      } ${className}`}
    >
      {on && <span className="h-2 w-2 rounded-full bg-sage" />}
    </span>
  );
}
