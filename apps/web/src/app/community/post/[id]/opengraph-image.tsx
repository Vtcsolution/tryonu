import { ImageResponse } from "next/og";
import { clip, loadSharePreview, plain } from "./share";

export const alt = "A look on TryOnU";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const INTERNAL = (process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

/** A picture as a data URI (fetched here, so the card never depends on the reader fetching it), or null. */
async function inline(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) return null;
    const type = res.headers.get("content-type") || "image/jpeg";
    if (!/image\/(jpeg|png)/.test(type)) return null;
    return `data:${type};base64,${Buffer.from(await res.arrayBuffer()).toString("base64")}`;
  } catch {
    return null;
  }
}

/** The card a shared post shows on LinkedIn, WhatsApp, Facebook, X: the look, and what it's wearing with prices. */
export default async function PostShareImage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const post = await loadSharePreview(id);
  const photo = post?.has_photo ? await inline(`${INTERNAL}/api/v1/community/share/${encodeURIComponent(id)}/photo.jpg`) : null;
  const shown = (post?.products ?? []).slice(0, 3);
  const thumbs = await Promise.all(
    shown.map((p) => (p.image_url ? inline(`${INTERNAL}/api/v1/img?u=${encodeURIComponent(p.image_url)}&w=240`) : Promise.resolve(null))),
  );
  const more = (post?.products.length ?? 0) - shown.length;
  const who = post ? post.author_name || `@${post.author_handle}` : "A TryOnU member";
  const caption = post?.caption ? clip(plain(post.caption), 110) : "";

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "linear-gradient(135deg, #141410 0%, #1f2a1d 100%)", color: "#f4f1e8" }}>
        {photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photo} alt="" width={440} height={630} style={{ width: 440, height: 630, objectFit: "cover" }} />
        ) : (
          <div style={{ width: 440, height: 630, display: "flex", alignItems: "center", justifyContent: "center", background: "#2a3327", fontSize: 120 }}>
            U
          </div>
        )}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "44px 48px", gap: 18 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: "#7d917a", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, fontWeight: 700, color: "#141410" }}>
              U
            </div>
            <div style={{ fontSize: 30, fontWeight: 700 }}>TryOnU</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 42, fontWeight: 700, lineHeight: 1.1 }}>{clip(`${who}'s look`, 34)}</div>
            {caption && <div style={{ fontSize: 24, color: "#c9c4b6", lineHeight: 1.3 }}>{caption}</div>}
          </div>
          {shown.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 4 }}>
              {shown.map((p, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 16, background: "rgba(255,255,255,0.08)", borderRadius: 18, padding: 10 }}>
                  {thumbs[i] ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={thumbs[i]!} alt="" width={64} height={64} style={{ width: 64, height: 64, borderRadius: 12, objectFit: "contain", background: "#ffffff" }} />
                  ) : (
                    <div style={{ width: 64, height: 64, borderRadius: 12, background: "#3a4436", display: "flex" }} />
                  )}
                  <div style={{ flex: 1, display: "flex", fontSize: 24 }}>{clip(plain(p.name), 34)}</div>
                  {p.price && <div style={{ display: "flex", fontSize: 26, fontWeight: 700, paddingRight: 8 }}>{p.price}</div>}
                </div>
              ))}
              {more > 0 && <div style={{ display: "flex", fontSize: 22, color: "#9fb59b" }}>+ {more} more in this look</div>}
            </div>
          )}
          <div style={{ marginTop: "auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", background: "#7d917a", color: "#141410", borderRadius: 999, padding: "12px 24px", fontSize: 24, fontWeight: 700 }}>
              Try it on yourself
            </div>
            <div style={{ display: "flex", fontSize: 24, color: "#9fb59b" }}>tryonu.app</div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
