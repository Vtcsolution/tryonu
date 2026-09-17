"use client";

import { useState } from "react";
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
import { ProductsTab, RetailersTab } from "./CatalogTabs";
import { CreditPackagesTab } from "./CreditPackagesTab";
import { TryOnsTab } from "./TryOnsTab";
import { UsersTab } from "./UsersTab";

const NAV = [
  { group: "Monitor", tabs: ["Overview", "System"] },
  { group: "Manage", tabs: ["Users", "Try-ons", "Products", "Retailers", "Credit packs"] },
  { group: "Money & activity", tabs: ["Payments", "Subscriptions", "Shop clicks", "AI usage", "Audit log"] },
] as const;

type Tab = (typeof NAV)[number]["tabs"][number];

export function AdminDashboard() {
  const { user, isLoading: sessionLoading } = useSession();
  const [tab, setTab] = useState<Tab>("Overview");

  if (sessionLoading) {
    return (
      <section className="mx-auto w-[min(1280px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  if (!user || !user.is_admin) {
    return (
      <section className="mx-auto w-[min(680px,calc(100%-42px))] py-24 text-center">
        <p className="font-display text-[20px] text-ink">Not authorized</p>
        <p className="mt-2 text-[14px] text-muted">This page is for TryOnU admins only.</p>
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(1280px,calc(100%-42px))] py-10 md:py-14">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h1 className="font-display text-[clamp(26px,4vw,38px)] leading-tight text-ink">
          Admin <em>panel</em>
        </h1>
        <p className="text-[12px] text-faint">Signed in as {user.email}</p>
      </div>

      <div className="mt-6 gap-8 lg:grid lg:grid-cols-[200px_1fr]">
        <nav aria-label="Admin sections" className="mb-6 lg:mb-0">
          <div className="flex gap-4 overflow-x-auto pb-2 lg:sticky lg:top-6 lg:flex-col lg:gap-5 lg:overflow-visible lg:pb-0">
            {NAV.map(({ group, tabs }) => (
              <div key={group} className="shrink-0">
                <p className="mb-1.5 hidden text-[10.5px] font-semibold uppercase tracking-[0.12em] text-faint lg:block">
                  {group}
                </p>
                <div className="flex gap-1.5 lg:flex-col lg:gap-0.5">
                  {tabs.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTab(t)}
                      aria-current={tab === t ? "page" : undefined}
                      className={`whitespace-nowrap rounded-full px-3.5 py-1.5 text-left text-[13px] transition-colors lg:rounded-[10px] ${
                        tab === t ? "bg-sage text-white" : "text-ink-soft hover:bg-paper-2"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </nav>

        <div className="min-w-0">
          {tab === "Overview" && <OverviewTab />}
          {tab === "System" && <SystemTab />}
          {tab === "Users" && <UsersTab currentAdminId={user.id} />}
          {tab === "Try-ons" && <TryOnsTab />}
          {tab === "Products" && <ProductsTab />}
          {tab === "Retailers" && <RetailersTab />}
          {tab === "Credit packs" && <CreditPackagesTab />}
          {tab === "Payments" && <PaymentsTab />}
          {tab === "Subscriptions" && <SubscriptionsTab />}
          {tab === "Shop clicks" && <AffiliateClicksTab />}
          {tab === "AI usage" && <AIUsageTab />}
          {tab === "Audit log" && <AuditLogTab />}
        </div>
      </div>
    </section>
  );
}
