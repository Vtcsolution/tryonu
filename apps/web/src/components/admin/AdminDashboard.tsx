"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { adminOps } from "@/lib/api/endpoints";
import { Logo } from "@/components/ui/Logo";
import { useSession } from "@/lib/auth/useSession";
import {
  AIUsageTab,
  AffiliateClicksTab,
  AuditLogTab,
  OverviewTab,
  PaymentsTab,
  SubscriptionsTab,
  SystemTab,
} from "./ActivityTabs";
import { AccountSettings } from "@/components/account/AccountSettings";
import { AdminShell, type NavGroup } from "./AdminShell";
import { AnalyticsTab } from "./AnalyticsTab";
import { ProductsTab, RetailersTab } from "./CatalogTabs";
import { CreditPackagesTab } from "./CreditPackagesTab";
import { StoresTab } from "./StoresTab";
import { DevelopersTab } from "./DevelopersTab";
import { FashnCreditsTab } from "./FashnCreditsTab";
import { SettingsTab } from "./SettingsTab";
import { TryOnsTab } from "./TryOnsTab";
import { UsersTab } from "./UsersTab";

type Tab =
  | "overview"
  | "analytics"
  | "users"
  | "tryons"
  | "products"
  | "retailers"
  | "packs"
  | "stores"
  | "settings"
  | "fashn"
  | "system"
  | "payments"
  | "subscriptions"
  | "clicks"
  | "ai-usage"
  | "audit"
  | "account"
  | "developers";

const NAV: readonly NavGroup<Tab>[] = [
  {
    group: "Monitor",
    tabs: [
      { id: "overview", label: "Overview", icon: "overview" },
      { id: "analytics", label: "Visitor analytics", icon: "analytics" },
    ],
  },
  {
    group: "Manage",
    tabs: [
      { id: "users", label: "Users", icon: "users" },
      { id: "tryons", label: "Try-ons", icon: "tryons" },
      { id: "products", label: "Products", icon: "products" },
      { id: "retailers", label: "Retailers", icon: "retailers" },
      { id: "packs", label: "Credit packs", icon: "packs" },
      { id: "stores", label: "Company stores", icon: "retailers" },
      { id: "developers", label: "Developer API", icon: "ai" },
    ],
  },
  {
    group: "Configure",
    tabs: [
      { id: "settings", label: "Settings & API keys", icon: "settings" },
      { id: "fashn", label: "FASHN credits", icon: "ai" },
      { id: "system", label: "System", icon: "system" },
    ],
  },
  {
    group: "Money & activity",
    tabs: [
      { id: "payments", label: "Payments", icon: "payments" },
      { id: "subscriptions", label: "Subscriptions", icon: "subscriptions" },
      { id: "clicks", label: "Shop clicks", icon: "clicks" },
      { id: "ai-usage", label: "AI usage", icon: "ai" },
      { id: "audit", label: "Audit log", icon: "audit" },
    ],
  },
  {
    group: "You",
    tabs: [
      { id: "account", label: "My account & password", icon: "users" },
    ],
  },
];

const TAB_IDS = new Set<string>(NAV.flatMap((g) => g.tabs.map((t) => t.id)));
const labelFor = (tab: Tab) => NAV.flatMap((g) => g.tabs).find((t) => t.id === tab)?.label ?? "";

function tabFromHash(): Tab {
  const hash = typeof window === "undefined" ? "" : window.location.hash.slice(1);
  return TAB_IDS.has(hash) ? (hash as Tab) : "overview";
}

export function AdminDashboard() {
  const { user, isLoading: sessionLoading } = useSession();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!sessionLoading && !user) {
      router.replace(`/sign-in?next=${encodeURIComponent(`/admin${window.location.hash}`)}`);
    }
  }, [sessionLoading, user, router]);

  // the current section lives in the URL hash (/admin#users) so a refresh,
  // bookmark or shared link opens the same section
  useEffect(() => {
    setTab(tabFromHash());
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    document.title = `${labelFor(tab)} · Admin · TryOnU`;
  }, [tab]);

  const selectTab = useCallback((next: Tab) => {
    setTab(next);
    window.history.replaceState(null, "", `#${next}`);
    window.scrollTo({ top: 0 });
  }, []);

  if (sessionLoading || !user) {
    return (
      <div className="grid min-h-screen place-items-center bg-paper">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="grid min-h-screen place-items-center bg-paper px-6">
        <div className="max-w-sm text-center">
          <Logo size={30} className="justify-center" />
          <p className="mt-6 font-display text-[22px] text-ink">Not authorized</p>
          <p className="mt-2 text-[15px] text-muted">
            You&rsquo;re signed in as {user.email}, which isn&rsquo;t an admin account.
          </p>
          <Link href="/" className="mt-5 inline-block text-[14px] text-sage-deep hover:underline">
            ← Back to TryOnU
          </Link>
        </div>
      </div>
    );
  }

  return (
    <AdminShell
      nav={NAV}
      active={tab}
      onSelect={selectTab}
      email={user.email}
      drawerOpen={drawerOpen}
      setDrawerOpen={setDrawerOpen}
    >
      {tab !== "fashn" && <FashnWarning onOpen={() => selectTab("fashn")} />}
      <div key={tab} className="tu-page">
        {tab === "overview" && <OverviewTab />}
        {tab === "analytics" && <AnalyticsTab />}
        {tab === "users" && <UsersTab currentAdminId={user.id} />}
        {tab === "tryons" && <TryOnsTab />}
        {tab === "products" && <ProductsTab />}
        {tab === "retailers" && <RetailersTab />}
        {tab === "packs" && <CreditPackagesTab />}
        {tab === "stores" && <StoresTab />}
        {tab === "developers" && <DevelopersTab />}
        {tab === "settings" && <SettingsTab />}
        {tab === "fashn" && <FashnCreditsTab />}
        {tab === "system" && <SystemTab />}
        {tab === "payments" && <PaymentsTab />}
        {tab === "subscriptions" && <SubscriptionsTab />}
        {tab === "clicks" && <AffiliateClicksTab />}
        {tab === "ai-usage" && <AIUsageTab />}
        {tab === "audit" && <AuditLogTab />}
        {tab === "account" && <AccountSettings user={user} />}
      </div>
    </AdminShell>
  );
}

/** Shoppers' try-ons run only while a FASHN approval is open: say so before customers find out. */
function FashnWarning({ onOpen }: { onOpen: () => void }) {
  const status = useQuery({ queryKey: ["admin", "fashn-approval"], queryFn: adminOps.fashnStatus, refetchInterval: 60_000 });
  if (!status.data) return null;
  const auto = status.data.automatic;
  const left = status.data.credits_left_now ?? 0;
  let text: string | null = null;
  let severe = false;
  if (auto?.paused) {
    text = "You paused automatic try-ons: every customer's try-on fails until you resume (their credits come back).";
    severe = true;
  } else if (!status.data.live_generation_allowed || left === 0) {
    text = "Try-ons are stopped: today's FASHN limit is used up. Raise it in Settings, or add extra credits.";
    severe = true;
  } else if (left < 8) {
    text = `Only ${left} FASHN credits left for today (about ${Math.floor(left / 4)} looks). Try-ons stop when they run out.`;
  }
  if (!text) return null;
  return (
    <div
      role="alert"
      className={`mb-5 flex flex-wrap items-center justify-between gap-3 rounded-[16px] border px-4 py-3 ${
        severe ? "border-[#c0503a]/40 bg-[#c0503a]/10" : "border-[#c9a13b]/50 bg-[#c9a13b]/10"
      }`}
    >
      <p className="text-[15px] font-medium text-ink">⚠ {text}</p>
      <button
        type="button"
        onClick={onOpen}
        className="tu-press min-h-[40px] rounded-full bg-sage px-4 text-[14px] font-semibold text-white hover:bg-sage-deep"
      >
        {auto?.paused ? "Resume →" : "Open FASHN credits →"}
      </button>
    </div>
  );
}
