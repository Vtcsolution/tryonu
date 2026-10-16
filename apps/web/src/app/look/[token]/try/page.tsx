import type { Metadata } from "next";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { TrySharedLook } from "@/components/try/TrySharedLook";

export const metadata: Metadata = { title: "Try this look on yourself", robots: { index: false, follow: false } };

type Props = { params: Promise<{ token: string }> };

/** Where a visitor lands after signing up from a shared look: the look's products become their own outfit. */
export default async function TrySharedLookPage({ params }: Props) {
  const { token } = await params;
  return (
    <SiteChrome>
      <TrySharedLook token={token} />
    </SiteChrome>
  );
}
