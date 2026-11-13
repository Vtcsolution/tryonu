import type { ReadyLook } from "@/lib/api/endpoints";

/** The look's title in words, then the first 8 characters of its id (titles can repeat or change). */
export function lookSlug(look: Pick<ReadyLook, "id" | "title">): string {
  const words = look.title
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .split("-")
    .slice(0, 10)
    .join("-");
  return `${words || "look"}-${look.id.slice(0, 8)}`;
}

export const lookPath = (look: Pick<ReadyLook, "id" | "title">) => `/looks/${lookSlug(look)}`;
