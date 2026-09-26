// frontend/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // required for production Docker image
  reactStrictMode: true,
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok.io"],
  experimental: {
    // Turbopack is enabled via `next dev --turbopack` in package.json scripts
  },
  async rewrites() {
    // Proxy /api/* → backend during development (avoids CORS in browser)
    return [
      {
        source: "/ws/:path*",
        destination: `${process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/ws/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
