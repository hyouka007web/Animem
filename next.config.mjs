/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
      { protocol: "http", hostname: "**" },
    ],
  },
  allowedDevOrigins: ["*.cloudshell.dev", "*.cs-europe-west1-haha.cloudshell.dev"],
};

export default nextConfig;
