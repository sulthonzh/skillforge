/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produce a fully static site (apps/web/out) that FastAPI can serve directly
  // in bundled mode, so `skillforge serve` runs one process on one port.
  output: "export",
  // No image optimizer in static-export mode.
  images: { unoptimized: true },
  // `output: "export"` forbids `rewrites()`. Cross-origin API access in dev is
  // handled client-side via NEXT_PUBLIC_API_URL (see lib/api.ts).
  trailingSlash: true,
};

module.exports = nextConfig;
