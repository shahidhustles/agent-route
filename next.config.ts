import type { NextConfig } from "next";

const BACKEND = process.env.ROUTER_BACKEND_URL ?? "http://127.0.0.1:8765";

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ["100.90.16.40", "192.168.1.40", "127.0.0.1", "thinkpad", "*.ts.net"],
  // The Python backend (routing/server.py) holds the router, the proxy, and the memory; the browser only sees /api/py.
  async rewrites() {
    return [{ source: "/api/py/:path*", destination: `${BACKEND}/:path*` }];
  },
  compress: false,
};

export default nextConfig;
