"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

// the console used to live at /developers: old links like /developers#keys still open it
const CONSOLE_TABS = new Set(["overview", "keys", "credits", "usage", "payments", "docs", "account"]);

export function OldConsoleLinks() {
  const router = useRouter();
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (CONSOLE_TABS.has(hash)) router.replace(`/developers/console#${hash}`);
  }, [router]);
  return null;
}
