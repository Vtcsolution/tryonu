import type { Metadata } from "next";
import { BusinessDashboard } from "@/components/business/BusinessDashboard";

export const metadata: Metadata = {
  title: "Sell on TryOnU",
  description: "Open your store on TryOnU: list your products where shoppers try them on, with local shoppers seeing you first.",
};

// A store gets its own panel with a sidebar (like the admin panel); before a
// store is opened, the page keeps the site's navbar and footer.
export default function BusinessPage() {
  return <BusinessDashboard />;
}
