import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  // Lean runtime image for Docker (see apps/web/Dockerfile) — bundles only
  // the traced production dependencies, not the whole node_modules tree.
  output: "standalone",
  // one address for every page: www.tryonu.app was a second copy of the site
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.tryonu.app" }],
        destination: "https://tryonu.app/:path*",
        permanent: true,
      },
    ];
  },
  images: {
    // Marketing photography (free, Unsplash). Retailer / CDN product-image
    // hosts get added here as product ingestion comes online.
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },
};

export default nextConfig;
