import type { Metadata } from "next";
import { AdminDashboard } from "@/components/admin/AdminDashboard";

export const metadata: Metadata = {
  title: "Admin",
  description: "Internal TryOnU operations dashboard.",
  robots: { index: false, follow: false },
};

// The admin area has its own dashboard shell (sidebar + top bar) instead of
// the public site's navbar and footer.
export default function AdminPage() {
  return <AdminDashboard />;
}
