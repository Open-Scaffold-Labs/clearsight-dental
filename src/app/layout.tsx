import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ClearSight Dental | AI X-Ray Analysis',
  description: 'Clinical-grade dental AI. Transparent, affordable, built by dentists.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  )
}