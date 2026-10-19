import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PreferencesWizard } from "@/components/preferences/PreferencesWizard";
import { MySizeCard } from "@/components/size/MySize";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Fashion preferences",
  description: "Pick the categories and styles you love so TryOnU can show you matching products.",
  robots: PRIVATE_PAGE,
};

export default function PreferencesPage() {
  return (
    <SiteChrome>
      <Suspense>
        <PreferencesWizard />
      </Suspense>
      <MySizeCard />
    </SiteChrome>
  );
}
