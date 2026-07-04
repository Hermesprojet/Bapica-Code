/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'localhost' },
      { protocol: 'https', hostname: '*.supabase.co' },
      { protocol: 'https', hostname: '*.vercel.app' },
    ],
  },
  poweredByHeader: false,
  reactStrictMode: true,
}

module.exports = nextConfig
