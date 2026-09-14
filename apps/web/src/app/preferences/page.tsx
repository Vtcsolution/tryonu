import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { PreferencesForm } from "@/components/preferences/PreferencesForm";

export const metadata: Metadata = {
  title: "Fashion preferences",
  description: "Set your styles, colors, brands, sizes, and budget to personalize your TryOnU recommendations.",
};

export default function PreferencesPage() {
  return (
    <SiteChrome>
      <Suspense>
        <PreferencesForm />
      </Suspense>
    </SiteChrome>
  );
}
