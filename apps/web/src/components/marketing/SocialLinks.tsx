import { SOCIAL_LINKS, type SocialName } from "@/lib/seo";

/** TryOnU's Instagram, TikTok, Facebook and LinkedIn as round icon links
 * (footer, phone menu, Me page). */
export function SocialLinks({ className = "", label, small = false }: { className?: string; label?: string; small?: boolean }) {
  return (
    <div className={className}>
      {label && <p className="mb-2 text-[12.5px] font-semibold uppercase tracking-[0.12em] text-faint">{label}</p>}
      <div className={`flex items-center ${small ? "gap-1.5" : "gap-2"}`} aria-label="TryOnU on social media">
        {SOCIAL_LINKS.map((s) => (
          <a
            key={s.name}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer me"
            aria-label={`TryOnU on ${s.name} (${s.handle})`}
            title={`${s.name}: ${s.handle}`}
            className={`grid ${small ? "h-10 w-10" : "h-11 w-11"} place-items-center rounded-full border border-line-strong text-ink-soft transition-colors hover:border-ink/40 hover:text-ink`}
          >
            <SocialIcon name={s.name} />
          </a>
        ))}
      </div>
    </div>
  );
}

function SocialIcon({ name }: { name: SocialName }) {
  const common = { width: 18, height: 18, viewBox: "0 0 24 24", "aria-hidden": true } as const;
  if (name === "LinkedIn") {
    return (
      <svg {...common} fill="currentColor">
        <rect x="3.5" y="9" width="3.6" height="11" rx=".4" />
        <circle cx="5.3" cy="5.3" r="2.1" />
        <path d="M9.6 9h3.4v1.6c.6-1 1.8-1.9 3.6-1.9 3 0 3.9 1.9 3.9 4.8V20h-3.6v-5.8c0-1.4-.3-2.6-1.8-2.6s-2 1.1-2 2.6V20H9.6V9z" />
      </svg>
    );
  }
  if (name === "Instagram") {
    return (
      <svg {...common} fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
      </svg>
    );
  }
  if (name === "TikTok") {
    return (
      <svg {...common} fill="currentColor">
        <path d="M16.6 3c.4 2.2 1.8 3.7 4 3.9v3.2c-1.5 0-2.8-.4-4-1.2v6.3c0 3.3-2.5 5.8-5.8 5.8S5 18.5 5 15.2c0-3.4 2.9-6 6.4-5.7v3.3c-1.5-.3-3 .8-3 2.4 0 1.4 1.1 2.5 2.4 2.5 1.4 0 2.6-1.1 2.6-2.6V3h3.2z" />
      </svg>
    );
  }
  return (
    <svg {...common} fill="currentColor">
      <path d="M13.5 21v-7.5h2.6l.4-3h-3V8.6c0-.9.3-1.5 1.5-1.5h1.6V4.4c-.3 0-1.2-.1-2.3-.1-2.3 0-3.8 1.4-3.8 3.9v2.3H8v3h2.5V21h3z" />
    </svg>
  );
}
