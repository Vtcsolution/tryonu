"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/lib/auth/useSession";

/** On phones, a signed-in member opening tryonu.app goes straight to their For you feed,
 * like opening an app; the welcome page is for visitors (and computers). */
export function PhoneHome() {
  const router = useRouter();
  const { user } = useSession();
  useEffect(() => {
    if (user && window.matchMedia("(max-width: 1023px)").matches) router.replace("/for-you");
  }, [user, router]);
  return null;
}
