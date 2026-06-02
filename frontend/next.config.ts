// next.config.ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',  // ← BARIS BARU, WAJIB untuk Docker
  async redirects() {
    return [
      {
        source: '/dashboard',
        destination: '/main/dashboard',
        permanent: true,
      },
    ]
  },
}

export default nextConfig