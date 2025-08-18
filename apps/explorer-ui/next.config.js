/** @type {import('next').NextConfig} */
const API_GATEWAY_URL = process.env.NEXT_PUBLIC_API_GATEWAY_URL || 'http://localhost:8000';
console.log('Next.js API_GATEWAY_URL =', API_GATEWAY_URL);

module.exports = {
  async rewrites() {
    return [
      // /api/v1/query  ->  http://localhost:8000/query
      // /api/v1/pack/123 -> http://localhost:8000/pack/123  (future)
      {
        source: '/api/v1/:path*',
        destination: `${API_GATEWAY_URL}/:path*`,
      },
    ];
  },
};