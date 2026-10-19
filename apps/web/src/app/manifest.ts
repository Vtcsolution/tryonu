import type { MetadataRoute } from "next";

/** "Add TryOnU to your home screen": opens full screen, like an app. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "TryOnU: try clothes on your own photo",
    short_name: "TryOnU",
    description: "See real products on your own photo before you buy, then shop from the original store.",
    start_url: "/?source=app",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#fbfaf6",
    theme_color: "#3b463c",
    categories: ["shopping", "lifestyle", "social"],
    icons: [
      { src: "/pwa/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/pwa/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/pwa/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Try on", url: "/try", icons: [{ src: "/pwa/icon-192.png", sizes: "192x192" }] },
      { name: "Community", url: "/community", icons: [{ src: "/pwa/icon-192.png", sizes: "192x192" }] },
      { name: "Notifications", url: "/notifications", icons: [{ src: "/pwa/icon-192.png", sizes: "192x192" }] },
    ],
  };
}
