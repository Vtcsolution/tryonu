import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { AccountPage } from "@/components/account/AccountPage";

export const metadata: Metadata = {
  title: "My account",
  description: "Change your name and password.",
  robots: { index: false, follow: false },
};

export default function Account() {
  return (
    <SiteChrome>
      <AccountPage />
    </SiteChrome>
  );
}
