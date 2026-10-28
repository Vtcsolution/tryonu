import type { Metadata } from "next";
import { AdminRedirect } from "@/components/admin/AdminRedirect";

export const metadata: Metadata = {
  title: "Admin",
  robots: { index: false, follow: false },
};

// the admin area lives at /admin/dashboard (and /admin/login)
export default function AdminPage() {
  return <AdminRedirect />;
}
