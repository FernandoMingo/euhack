/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/slidedeck", destination: "/slidedeck.html" },
    ];
  },
};

export default nextConfig;
