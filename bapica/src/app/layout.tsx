import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Toaster } from "sonner"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Hermes SaaS — Agents IA pour votre entreprise",
  description:
    "Plateforme multi-agents IA pour PME et indépendants. Prospection, support, contenu, voix, recrutement, comptabilité et plus encore.",
  keywords: ["IA", "agents", "PME", "prospection", "support client", "SaaS"],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={inter.className}>
        {children}
        <Toaster position="bottom-right" richColors />
      </body>
    </html>
  )
}
