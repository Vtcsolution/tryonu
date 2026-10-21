import { serverFetch } from "@/lib/api/server";

/** What a shared post shows on LinkedIn, WhatsApp, Facebook, X… (readable without signing in). */
export type SharePreview = {
  id: string;
  author_handle: string;
  author_name: string | null;
  caption: string | null;
  media_kind: string;
  has_photo: boolean;
  products: { name: string; price: string | null; image_url: string | null }[];
};

export function loadSharePreview(id: string): Promise<SharePreview | null> {
  return serverFetch<SharePreview>(`/api/v1/community/share/${encodeURIComponent(id)}`, { revalidateSeconds: 300 });
}

// emoji have no font in the share card; plain words read the same everywhere
export const plain = (text: string) => text.replace(/\p{Extended_Pictographic}|️|‍/gu, "").replace(/\s+/g, " ").trim();

export const clip = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);

export function shareWords(p: SharePreview) {
  const who = p.author_name || `@${p.author_handle}`;
  const title = `${who}'s look on TryOnU`;
  const wearing = p.products
    .slice(0, 4)
    .map((x) => (x.price ? `${clip(x.name, 50)} (${x.price})` : clip(x.name, 50)))
    .join(", ");
  const caption = p.caption ? plain(p.caption) : "";
  const description = [caption && clip(caption, 160), wearing && `Wearing: ${wearing}`, "Try it on yourself with TryOnU."]
    .filter(Boolean)
    .join(" · ");
  return { title, description };
}
