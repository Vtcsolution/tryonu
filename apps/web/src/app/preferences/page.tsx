import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PreferencesWizard } from "@/components/preferences/PreferencesWizard";

export const metadata: Metadata = {
  title: "Fashion preferences",
  description: "Pick the categories and styles you love so TryOnU can show you matching products.",
};

export default function PreferencesPage() {
  return (
    <SiteChrome>
      <Suspense>
        <PreferencesWizard />
      </Suspense>
    </SiteChrome>
  );
}
