import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'IG Scraper — Instagram Analytics Dashboard',
  description: 'Scrape Instagram posts, analyze sentiment, track followers.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="bg-mesh min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}
