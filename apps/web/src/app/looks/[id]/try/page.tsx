import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { TryReadyLook } from "@/components/looks/TryReadyLook";

export const metadata: Metadata = { title: "Try this look on you", robots: { index: false, follow: false } };

type Props = { params: Promise<{ id: string }> };

/** After "Try this look on you first" (and sign-up, when needed): the look's
 * products become the shopper's own outfit on the try-on page. */
export default async function TryReadyLookPage({ params }: Props) {
  const { id } = await params;
  return (
    <SiteChrome>
      <TryReadyLook lookId={id} />
    </SiteChrome>
  );
}
