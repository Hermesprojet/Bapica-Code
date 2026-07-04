import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { ToastProvider } from "@/components/ui/toast"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Bapica — Agents IA pour votre entreprise",
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
    <html lang="fr" className="dark" style={{ colorScheme: "dark" }} suppressHydrationWarning>
      <body className={inter.className}>
        <ToastProvider>
          {children}
        </ToastProvider>
      </body>
    </html>
  )
}
