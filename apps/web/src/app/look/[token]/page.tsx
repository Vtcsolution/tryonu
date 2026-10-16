import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { SharedLookView } from "@/components/try/SharedLookView";
import { serverFetch } from "@/lib/api/server";
import type { SharedLook } from "@/lib/api/types";

type Props = { params: Promise<{ token: string }> };

async function load(token: string): Promise<SharedLook | null> {
  return serverFetch<SharedLook>(`/api/v1/shared/${encodeURIComponent(token)}`, { revalidateSeconds: 30 });
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const look = await load((await params).token);
  if (!look) return { title: "Look not found", robots: { index: false, follow: false } };
  const pieces = look.products.map((p) => p.name).slice(0, 3).join(" · ");
  const description = pieces ? `Tried on with AI: ${pieces}. See it on you with TryOnU.` : "A look tried on with AI on TryOnU.";
  return {
    title: `${look.title}: a look on TryOnU`,
    description,
    robots: { index: false, follow: false },
    openGraph: {
      title: `${look.title}: tried on with TryOnU`,
      description,
      images: [{ url: look.image_url, alt: look.title }],
      type: "article",
    },
    twitter: { card: "summary_large_image", title: `${look.title}: tried on with TryOnU`, description, images: [look.image_url] },
  };
}

export default async function SharedLookPage({ params }: Props) {
  const look = await load((await params).token);
  if (!look) notFound();
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "tryonu.app";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  return (
    <SiteChrome>
      <SharedLookView look={look} pageUrl={`${proto}://${host}/look/${look.token}`} />
    </SiteChrome>
  );
}
