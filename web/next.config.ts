import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

// External URL rewrites are proxied by Next with http-proxy. Default proxyTimeout is 30s,
// which cuts off slow LLM responses and surfaces as ECONNRESET / "socket hang up".
const proxyTimeoutMs = Number(process.env.BACKEND_PROXY_TIMEOUT_MS ?? "300000");

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    proxyTimeout: proxyTimeoutMs,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
