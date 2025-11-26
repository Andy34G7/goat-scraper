import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // No rewrites needed - files served from public/ automatically
};

export default nextConfig;
