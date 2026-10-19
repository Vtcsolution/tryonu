import type { Metadata } from "next";
import { PriceAlertsPage } from "@/components/alerts/PriceAlerts";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = { title: "Price alerts", robots: PRIVATE_PAGE };

export default function AlertsPage() {
  return (
    <SiteChrome>
      <PriceAlertsPage />
    </SiteChrome>
  );
}
