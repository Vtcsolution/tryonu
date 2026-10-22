import { DevChrome } from "@/components/developers/DevChrome";
import { DevHome } from "@/components/developers/DevHome";
import { serverFetch } from "@/lib/api/server";
import type { DeveloperCreditPack } from "@/lib/api/types";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "TryOnU Developers: Virtual Try-On API",
  description:
    "Add AI virtual try-on to your website or app: a REST API, a no-code website widget, and WordPress, WooCommerce and Shopify plugins. Pay per try-on.",
  path: "/developers",
  keywords: ["virtual try on API", "try on API", "AI fitting room API"],
});

export default async function DevelopersHomePage() {
  const packs = (await serverFetch<DeveloperCreditPack[]>("/api/v1/developers/packs", { revalidateSeconds: 300 })) ?? [];
  return (
    <DevChrome>
      <DevHome packs={packs} />
    </DevChrome>
  );
}
