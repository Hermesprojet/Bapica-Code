import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Inscription — Créez votre équipe d'agents IA en 2 minutes",
  description:
    "Créez votre compte Bapica et déployez votre équipe d'agents IA en 2 minutes. Essai gratuit 15 jours, sans engagement ni carte bancaire.",
  keywords: [
    "inscription Bapica",
    "essai gratuit agents IA",
    "créer compte IA",
    "démo agents IA",
  ],
  robots: {
    index: false,
    follow: false,
  },
}

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return children
}
