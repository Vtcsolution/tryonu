import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { BusinessDashboard } from "@/components/business/BusinessDashboard";

export const metadata: Metadata = {
  title: "Sell on TryOnU",
  description: "Open your store on TryOnU: list your products where shoppers try them on, with local shoppers seeing you first.",
};

export default function BusinessPage() {
  return (
    <SiteChrome>
      <BusinessDashboard />
    </SiteChrome>
  );
}
