import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { ToastProvider } from "@/components/ui/toast"
import { CookieBanner } from "@/components/ui/cookie-banner"
import {
  getOrganizationSchema,
  getWebSiteSchema,
  JsonLdScript,
} from "@/lib/jsonld"

const inter = Inter({ subsets: ["latin"] })

const baseUrl = "https://bapica.com"

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),

  title: {
    default: "Bapica — Agents IA pour votre entreprise",
    template: "%s | Bapica",
  },

  description:
    "Plateforme multi-agents IA pour PME et indépendants. Prospection, support client, contenu, voix, recrutement, comptabilité et plus encore. 13 agents spécialisés, messagerie illimitée, essai gratuit 15 jours.",

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
      "13 agents IA qui collaborent entre eux, orchestrés par Léo. Prospection, support, contenu, voix, recrutement, comptabilité. Essai gratuit 15 jours.",
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
      "13 agents IA qui collaborent entre eux, orchestrés par Léo. Prospection, support, contenu, voix, recrutement, comptabilité. Essai gratuit 15 jours.",
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

  // App icons (SVG for modern browsers, ICO fallback)
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico" },
    ],
    apple: "/apple-icon.png",
    other: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  },

  // Google Search Console — supprimer ce bloc et ajouter le vrai code
  // quand il sera disponible. En attendant, pas de balise de vérification.

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
        {/* PWA */}
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#061126" />
        {/* JSON-LD Structured Data */}
        <JsonLdScript data={getOrganizationSchema() as unknown as Record<string, unknown>} />
        <JsonLdScript data={getWebSiteSchema() as unknown as Record<string, unknown>} />
      </head>
      <body className={inter.className}>
        <script dangerouslySetInnerHTML={{ __html: `
          // Force scroll to top on page load/refresh
          if ('scrollRestoration' in history) {
            history.scrollRestoration = 'manual';
          }
          window.addEventListener('beforeunload', () => {
            window.scrollTo(0, 0);
          });
          
          // Register Service Worker for PWA
          if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
              navigator.serviceWorker.register('/sw.js').then(() => {
                if (process.env.NODE_ENV === 'development') console.log('SW registered');
              }).catch(() => {});
            });
          }
        `}} />
        <ToastProvider>
          {children}
          <CookieBanner />
        </ToastProvider>
      </body>
    </html>
  )
}
