import type { Metadata } from "next";
import { DeveloperPortal } from "@/components/developers/DeveloperPortal";

export const metadata: Metadata = {
  title: "Developer portal",
  description: "Add TryOnU's virtual try-on to your own shop or app: API keys, credits, usage and code.",
  robots: { index: false, follow: false },
};

export default function DevelopersPage() {
  return <DeveloperPortal />;
}
