/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:3004/api/v1/:path*', // KEEP /api/v1
      },
    ];
  },
};
module.exports = nextConfig;
