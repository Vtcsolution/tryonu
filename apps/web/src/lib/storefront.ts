import { serverFetch } from "@/lib/api/server";
import type { PublicStore } from "@/lib/api/types";

/** A store's own page data (tryonu.app/<store>), fetched on the server; null when no such open store. */
export function loadStore(slug: string) {
  // the website's own pages never get here (they're matched first), and a
  // store slug is lowercase letters, digits and dashes
  if (!/^[a-z0-9][a-z0-9-]{0,139}$/.test(slug)) return Promise.resolve(null);
  return serverFetch<PublicStore>(`/api/v1/stores/public/${encodeURIComponent(slug)}`, { revalidateSeconds: 120 });
}
