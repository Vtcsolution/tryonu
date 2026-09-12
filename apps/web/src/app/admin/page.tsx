import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { AdminDashboard } from "@/components/admin/AdminDashboard";

export const metadata: Metadata = {
  title: "Admin",
  description: "Internal TryOnU operations dashboard.",
};

export default function AdminPage() {
  return (
    <SiteChrome>
      <AdminDashboard />
    </SiteChrome>
  );
}
