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
  openGraph: {
    title: "Bapica — Des agents IA qui travaillent en équipe pour votre entreprise",
    description:
      "Jusqu'à 12 agents IA qui collaborent entre eux, orchestrés par Léo. Prospection, support, contenu, voix, recrutement, comptabilité.",
    url: "https://bapica.com",
    siteName: "Bapica",
    locale: "fr_FR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Bapica — Agents IA pour votre entreprise",
    description:
      "Jusqu'à 12 agents IA qui collaborent entre eux, orchestrés par Léo.",
  },
  metadataBase: new URL("https://bapica.com"),
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={inter.className}>
        <ToastProvider>
          {children}
        </ToastProvider>
      </body>
    </html>
  )
}
