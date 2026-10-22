/** The developer portal is a site of its own: links to it from the shopping site open in a new window. */
export const isDevPortal = (href: string) => href === "/developers" || href.startsWith("/developers/") || href.startsWith("/developers#");
