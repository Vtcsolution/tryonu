import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { NotificationsPage } from "@/components/notifications/NotificationsPage";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Notifications",
  description: "Likes, comments, replies, new followers and credits on TryOnU.",
  robots: PRIVATE_PAGE,
};

export default function Notifications() {
  return (
    <SiteChrome>
      <NotificationsPage />
    </SiteChrome>
  );
}
