import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Connexion — Accédez à votre équipe d'agents IA",
  description:
    "Connectez-vous à votre compte Bapica pour accéder à vos agents IA spécialisés, votre tableau de bord et vos automatisations.",
  robots: {
    index: false,
    follow: false,
  },
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children
}
