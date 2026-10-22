import type { Metadata } from "next";
import { DeveloperPortal } from "@/components/developers/DeveloperPortal";

export const metadata: Metadata = {
  title: "Developer console",
  description: "Your TryOnU API keys, credits, usage and payments.",
  robots: { index: false, follow: false },
};

export default function DeveloperConsolePage() {
  return <DeveloperPortal />;
}
