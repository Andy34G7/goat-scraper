import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  output: "standalone",
  // No rewrites needed - files served from public/ automatically
};

export default nextConfig;
