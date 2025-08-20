// apps/explorer-ui/next.config.js
module.exports = {
  async rewrites() {
    return [
      { 
        source: '/api/v1/:path*', 
        destination: 'https://gaea-gateway-783449213067.us-central1.run.app/api/v1/:path*' 
      }
    ];
  },
};
