import type { NextConfig } from 'next'

const config: NextConfig = {
  async rewrites() {
    return [
      {
        // Semua /api/* dari frontend diteruskan ke FastAPI di port 8000
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ]
  },
  images: {
    remotePatterns: [
      { hostname: 'cdninstagram.com' },
      { hostname: '*.cdninstagram.com' },
      { hostname: 'instagram.com' },
    ],
  },
}

export default config
