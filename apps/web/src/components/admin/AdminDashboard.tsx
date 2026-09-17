"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
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
import { AdminShell, type NavGroup } from "./AdminShell";
import { ProductsTab, RetailersTab } from "./CatalogTabs";
import { CreditPackagesTab } from "./CreditPackagesTab";
import { SettingsTab } from "./SettingsTab";
import { TryOnsTab } from "./TryOnsTab";
import { UsersTab } from "./UsersTab";

type Tab =
  | "overview"
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
  | "ai-usage"
  | "audit";

const NAV: readonly NavGroup<Tab>[] = [
  { group: "Monitor", tabs: [{ id: "overview", label: "Overview", icon: "overview" }] },
  {
    group: "Manage",
    tabs: [
      { id: "users", label: "Users", icon: "users" },
      { id: "tryons", label: "Try-ons", icon: "tryons" },
      { id: "products", label: "Products", icon: "products" },
      { id: "retailers", label: "Retailers", icon: "retailers" },
      { id: "packs", label: "Credit packs", icon: "packs" },
    ],
  },
  {
    group: "Configure",
    tabs: [
      { id: "settings", label: "Settings & API keys", icon: "settings" },
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
          <p className="mt-2 text-[14px] text-muted">
            You&rsquo;re signed in as {user.email}, which isn&rsquo;t an admin account.
          </p>
          <Link href="/" className="mt-5 inline-block text-[13px] text-sage-deep hover:underline">
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
      {tab === "overview" && <OverviewTab />}
      {tab === "users" && <UsersTab currentAdminId={user.id} />}
      {tab === "tryons" && <TryOnsTab />}
      {tab === "products" && <ProductsTab />}
      {tab === "retailers" && <RetailersTab />}
      {tab === "packs" && <CreditPackagesTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "system" && <SystemTab />}
      {tab === "payments" && <PaymentsTab />}
      {tab === "subscriptions" && <SubscriptionsTab />}
      {tab === "clicks" && <AffiliateClicksTab />}
      {tab === "ai-usage" && <AIUsageTab />}
      {tab === "audit" && <AuditLogTab />}
    </AdminShell>
  );
}
