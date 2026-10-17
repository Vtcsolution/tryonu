import { ImageResponse } from "next/og";

export const alt = "TryOnU: try real fashion on you before you buy";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** The picture shown when a TryOnU link is shared (pages without their own). */
export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: "linear-gradient(135deg, #141410 0%, #1f2a1d 100%)",
          color: "#f4f1e8",
          fontFamily: "serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              background: "#7d917a",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 40,
              color: "#141410",
              fontWeight: 700,
            }}
          >
            U
          </div>
          <div style={{ fontSize: 44, fontWeight: 700, letterSpacing: -1 }}>TryOnU</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ fontSize: 76, lineHeight: 1.05, letterSpacing: -2 }}>Try real fashion on you before you buy.</div>
          <div style={{ fontSize: 30, color: "#c9c4b6", fontFamily: "sans-serif" }}>
            AI virtual try-on: real products from real stores, on your own photo.
          </div>
        </div>
        <div style={{ fontSize: 28, color: "#9fb59b", fontFamily: "sans-serif" }}>tryonu.app</div>
      </div>
    ),
    size,
  );
}
