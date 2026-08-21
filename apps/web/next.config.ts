import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Monorepo içindeki paylaşılan TypeScript paketleri kaynak halde derlenir.
  transpilePackages: ["@krizkalkan/types"],
};

export default nextConfig;
