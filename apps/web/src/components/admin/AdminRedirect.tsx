"use client";

import { useEffect } from "react";

/** /admin: on to the dashboard, keeping the section (/admin#users). */
export function AdminRedirect() {
  useEffect(() => {
    window.location.replace(`/admin/dashboard${window.location.hash}`);
  }, []);
  return null;
}
