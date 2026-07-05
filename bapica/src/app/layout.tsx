import type { Metadata } from "next"
import { Manrope } from "next/font/google"
import "./globals.css"
import { ToastProvider } from "@/components/ui/toast"
import { CookieBanner } from "@/components/ui/cookie-banner"
import {
  getOrganizationSchema,
  getWebSiteSchema,
  JsonLdScript,
} from "@/lib/jsonld"

const manrope = Manrope({ subsets: ["latin"] })

const baseUrl = "https://bapica.com"

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),

  title: {
    default: "Bapica — Agents IA pour votre entreprise",
    template: "%s — Bapica",
  },

  description:
    "Plateforme multi-agents IA pour PME et indépendants. Prospection, support client, contenu, voix, recrutement, comptabilité et plus encore. 12 agents spécialisés, messagerie illimitée, essai gratuit 14 jours.",

  keywords: [
    "agents IA",
    "intelligence artificielle",
    "PME",
    "indépendants",
    "automatisation",
    "prospection commerciale",
    "support client IA",
    "création de contenu IA",
    "agent téléphonique IA",
    "comptabilité automatisée",
    "SaaS français",
    "IA pour entreprise",
    "assistant IA",
    "automatisation PME",
    "Bapica",
  ],

  openGraph: {
    title: "Bapica — Des agents IA qui travaillent en équipe pour votre entreprise",
    description:
      "Jusqu'à 12 agents IA qui collaborent entre eux, orchestrés par Léo. Prospection, support, contenu, voix, recrutement, comptabilité. Essai gratuit 14 jours.",
    url: baseUrl,
    siteName: "Bapica",
    locale: "fr_FR",
    type: "website",
    images: [
      {
        url: `${baseUrl}/opengraph-image`,
        width: 1200,
        height: 630,
        alt: "Bapica — Agents IA pour votre entreprise",
      },
    ],
  },

  twitter: {
    card: "summary_large_image",
    title: "Bapica — Agents IA pour votre entreprise",
    description:
      "Jusqu'à 12 agents IA qui collaborent entre eux, orchestrés par Léo. Prospection, support, contenu, voix, recrutement, comptabilité. Essai gratuit 14 jours.",
    images: [`${baseUrl}/opengraph-image`],
  },

  alternates: {
    canonical: "/",
    languages: {
      fr: baseUrl,
    },
  },

  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },

  // App icons
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-icon.png",
  },

  // Verification for Google Search Console (à remplacer par la vraie valeur)
  // verification: {
  //   google: "VOTRE_CODE_GOOGLE_SEARCH_CONSOLE",
  // },

  category: "technology",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head>
        {/* JSON-LD Structured Data */}
        <JsonLdScript data={getOrganizationSchema() as unknown as Record<string, unknown>} />
        <JsonLdScript data={getWebSiteSchema() as unknown as Record<string, unknown>} />
      </head>
      <body className={manrope.className}>
        <ToastProvider>
          {children}
          <CookieBanner />
        </ToastProvider>
      </body>
    </html>
  )
}
