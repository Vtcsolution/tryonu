import { SiteChrome } from "@/components/layout/SiteChrome";
import { GetTheApp } from "@/components/pwa/InstallApp";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Get the TryOnU App on iPhone and Android",
  description:
    "Add TryOnU to your iPhone or Android home screen in seconds: opens in one tap, full screen, with notifications. Free, no app store needed.",
  path: "/app",
  keywords: ["TryOnU app", "virtual try on app iPhone", "virtual try on app Android"],
});

export default function AppPage() {
  return (
    <SiteChrome>
      <GetTheApp />
    </SiteChrome>
  );
}
