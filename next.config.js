/** @type {import('next').NextConfig} */
const nextConfig = {
  rewrites: async () => {
    return [
      {
        // En desarrollo, FastAPI corre aparte en :8000. En producción (Vercel),
        // api/index.py se sirve como serverless function bajo /api/.
        source: '/api/py/:path*',
        destination:
          process.env.NODE_ENV === 'development'
            ? 'http://127.0.0.1:8000/api/py/:path*'
            : '/api/',
      },
    ];
  },
};

module.exports = nextConfig;
