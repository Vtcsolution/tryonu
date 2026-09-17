"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { useLogout } from "@/lib/auth/useSession";

export type NavGroup<T extends string> = { group: string; tabs: readonly { id: T; label: string; icon: IconName }[] };

export function AdminShell<T extends string>({
  nav,
  active,
  onSelect,
  email,
  drawerOpen,
  setDrawerOpen,
  children,
}: {
  nav: readonly NavGroup<T>[];
  active: T;
  onSelect: (tab: T) => void;
  email: string;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  children: ReactNode;
}) {
  const activeGroup = nav.find((g) => g.tabs.some((t) => t.id === active));
  const activeLabel = activeGroup?.tabs.find((t) => t.id === active)?.label ?? "";
  const drawerRef = useRef<HTMLDivElement>(null);

  // drawer: Escape closes, page behind doesn't scroll, focus moves into it
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    drawerRef.current?.querySelector<HTMLElement>("button, a")?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [drawerOpen, setDrawerOpen]);

  const sidebar = (
    <SidebarContent
      nav={nav}
      active={active}
      email={email}
      onSelect={(tab) => {
        onSelect(tab);
        setDrawerOpen(false);
      }}
    />
  );

  return (
    <div className="min-h-screen bg-paper lg:grid lg:grid-cols-[264px_minmax(0,1fr)]">
      <aside className="hidden border-r border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        {sidebar}
      </aside>

      <div className={`fixed inset-0 z-50 lg:hidden ${drawerOpen ? "" : "pointer-events-none"}`} aria-hidden={!drawerOpen}>
        <div
          className={`absolute inset-0 bg-black/45 transition-opacity duration-300 ${drawerOpen ? "opacity-100" : "opacity-0"}`}
          onClick={() => setDrawerOpen(false)}
        />
        <div
          ref={drawerRef}
          role="dialog"
          aria-modal="true"
          aria-label="Admin navigation"
          inert={!drawerOpen}
          className={`absolute inset-y-0 left-0 flex w-[min(288px,85vw)] flex-col bg-surface shadow-lift transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
            drawerOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {sidebar}
        </div>
      </div>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-line bg-paper/85 px-4 backdrop-blur sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
            className="-ml-1 grid h-10 w-10 place-items-center rounded-full text-ink-soft hover:bg-ink/[0.06] lg:hidden"
          >
            <Icon name="menu" />
          </button>
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
            <span className="hidden text-faint sm:inline">Admin</span>
            <span className="hidden text-faint sm:inline" aria-hidden="true">/</span>
            <span className="hidden text-faint sm:inline">{activeGroup?.group}</span>
            <span className="hidden text-faint sm:inline" aria-hidden="true">/</span>
            <span className="truncate font-medium text-ink">{activeLabel}</span>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link
              href="/"
              className="hidden h-9 items-center gap-1.5 rounded-full border border-line px-3.5 text-[12.5px] text-ink-soft transition-colors hover:border-line-strong hover:text-ink sm:inline-flex"
            >
              <Icon name="external" size={15} />
              View site
            </Link>
            <ThemeToggle />
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-[1240px]">{children}</div>
        </main>
      </div>
    </div>
  );
}

function SidebarContent<T extends string>({
  nav,
  active,
  email,
  onSelect,
}: {
  nav: readonly NavGroup<T>[];
  active: T;
  email: string;
  onSelect: (tab: T) => void;
}) {
  const router = useRouter();
  const logout = useLogout();

  return (
    <>
      <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-line px-5">
        <Logo size={26} href="/admin" />
        <span className="rounded-md bg-sage px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-white">
          Admin
        </span>
      </div>

      <nav aria-label="Admin sections" className="flex-1 overflow-y-auto px-3 py-4">
        {nav.map(({ group, tabs }) => (
          <div key={group} className="mb-5 last:mb-0">
            <p className="mb-1.5 px-3 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-faint">{group}</p>
            <ul className="space-y-0.5">
              {tabs.map((t) => {
                const isActive = t.id === active;
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(t.id)}
                      aria-current={isActive ? "page" : undefined}
                      className={`flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-left text-[13.5px] transition-colors ${
                        isActive ? "bg-sage text-white" : "text-ink-soft hover:bg-paper-2 hover:text-ink"
                      }`}
                    >
                      <Icon name={t.icon} size={17} />
                      {t.label}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-line p-3">
        <div className="flex items-center gap-2.5 rounded-[12px] px-2 py-2">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-sage text-[13px] font-semibold uppercase text-white">
            {email.charAt(0)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[12.5px] font-medium text-ink" title={email}>
              {email}
            </p>
            <p className="text-[11px] text-faint">Administrator</p>
          </div>
        </div>
        <div className="mt-1 grid grid-cols-2 gap-2">
          <Link
            href="/"
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-full border border-line text-[12px] text-ink-soft hover:border-line-strong hover:text-ink"
          >
            <Icon name="external" size={14} />
            Site
          </Link>
          <button
            type="button"
            disabled={logout.isPending}
            onClick={() => logout.mutate(undefined, { onSuccess: () => router.replace("/sign-in") })}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-full border border-line text-[12px] text-ink-soft hover:border-[#c0503a]/40 hover:text-[#a4553f] disabled:opacity-50"
          >
            <Icon name="logout" size={14} />
            Sign out
          </button>
        </div>
      </div>
    </>
  );
}

export type IconName =
  | "overview"
  | "analytics"
  | "users"
  | "tryons"
  | "products"
  | "retailers"
  | "packs"
  | "settings"
  | "system"
  | "payments"
  | "subscriptions"
  | "clicks"
  | "ai"
  | "audit"
  | "menu"
  | "external"
  | "logout";

const PATHS: Record<IconName, string> = {
  overview: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  analytics: "M3 20h18M6 16v-4M11 16V8M16 16v-6M21 16V5",
  users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a7 7 0 0 1 14 0v1M16 3.5a4 4 0 0 1 0 7.5M22 21v-1a7 7 0 0 0-4-6.3",
  tryons: "M12 3l1.8 4.9L19 9.7l-5.2 1.8L12 16l-1.8-4.5L5 9.7l5.2-1.8zM18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z",
  products: "M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9zM7.5 7.5h.01",
  retailers: "M3 9l1.5-5h15L21 9M3 9v11h18V9M3 9h18M9 20v-6h6v6",
  packs: "M12 7c4.4 0 8-1.3 8-3s-3.6-3-8-3-8 1.3-8 3 3.6 3 8 3zM4 4v8c0 1.7 3.6 3 8 3s8-1.3 8-3V4M4 12v8c0 1.7 3.6 3 8 3s8-1.3 8-3v-8",
  settings: "M15 7a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM3 7h12M19 7h2M5 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM3 17h2M9 17h12",
  system: "M3 4h18v7H3zM3 13h18v7H3zM7 7.5h.01M7 16.5h.01",
  payments: "M2 6h20v12H2zM2 10h20M6 15h4",
  subscriptions: "M17 2l4 4-4 4M3 11v-1a4 4 0 0 1 4-4h14M7 22l-4-4 4-4M21 13v1a4 4 0 0 1-4 4H3",
  clicks: "M7 17L17 7M8 7h9v9",
  ai: "M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2M6 6h12v12H6zM10 10h4v4h-4z",
  audit: "M9 4h6a1 1 0 0 1 1 1v1H8V5a1 1 0 0 1 1-1zM8 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-2M9 12h6M9 16h4",
  menu: "M4 7h16M4 12h16M4 17h16",
  external: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  logout: "M15 17l5-5-5-5M20 12H9M11 20H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h6",
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className="shrink-0">
      <path d={PATHS[name]} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
