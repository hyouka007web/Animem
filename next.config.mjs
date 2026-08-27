/** @type {import('next').NextConfig} */

const pbUrl = new URL(process.env.NEXT_PUBLIC_POCKETBASE_URL || "http://127.0.0.1:8090");
const imageHosts = (process.env.ANIMEM_IMAGE_HOSTS || "")
  .split(",")
  .map((host) => host.trim().toLowerCase())
  .filter(Boolean);

const remotePatterns = [
  { protocol: pbUrl.protocol.replace(":", ""), hostname: pbUrl.hostname, port: pbUrl.port },
  ...imageHosts.map((hostname) => ({ protocol: "https", hostname })),
];

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  images: { remotePatterns },
  allowedDevOrigins: ["*.cloudshell.dev", "*.cs-europe-west1-haha.cloudshell.dev"],
};

export default nextConfig;
