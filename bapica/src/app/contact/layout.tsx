import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Contactez-nous — Parlez à un expert IA",
  description:
    "Une question sur Bapica ou nos agents IA ? Contactez notre équipe. Nous répondons en moins de 24h. Essai gratuit 15 jours, sans engagement.",
  keywords: [
    "contact Bapica",
    "contacter Bapica",
    "support Bapica",
    "démo agents IA",
    "question Bapica",
  ],
  alternates: {
    canonical: "https://bapica.com/contact",
  },
  openGraph: {
    title: "Contactez Bapica — Parlez à un expert de nos agents IA",
    description:
      "Une question sur nos agents IA ou nos formules ? Contactez-nous, réponse sous 24h.",
  },
}

export default function ContactLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}
